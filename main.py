from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from crewai import Crew, Process
from agents import DataCollectorAgent, DataFormatterAgent, SummaryGeneratorAgent
from tools import FinanceTools
import json
import os
import re
import time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

finance_tools = FinanceTools()

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            company_input = data.strip()
            
            await websocket.send_json({"type": "thinking", "status": True})
            
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    collector_agent = DataCollectorAgent()
                    formatter_agent = DataFormatterAgent()
                    summary_agent = SummaryGeneratorAgent()
                    
                    crew = Crew(
                        agents=[collector_agent.agent, formatter_agent.agent, summary_agent.agent],
                        tasks=[
                            collector_agent.create_task(company_input, finance_tools, websocket),
                            formatter_agent.create_task(),
                            summary_agent.create_task()
                        ],
                        process=Process.sequential,
                        verbose=True
                    )
                    
                    result = crew.kickoff()
                    
                    # Extract task outputs
                    collector_output = result.tasks_output[0].raw
                    formatter_output = result.tasks_output[1].raw
                    summary_output = result.tasks_output[2].raw
                    
                    # Handle error messages
                    if isinstance(collector_output, str):
                        if "Error" in collector_output or "inventory-based" in collector_output or "No data available" in collector_output:
                            await websocket.send_json({
                                "type": "message",
                                "content": collector_output
                            })
                            break
                        # Parse embedded JSON from string
                        json_match = re.search(r'\{.*\}', collector_output, re.DOTALL)
                        if json_match:
                            try:
                                json_str = json_match.group(0)
                                json_str = json_str.replace(r'\\$', '$')
                                financial_data = json.loads(json_str)
                                summary = collector_output.replace(json_str, "").strip() or summary_output or "Financial data collected."
                                await websocket.send_json({
                                    "type": "result",
                                    "data": {
                                        "financial_data": financial_data,
                                        "summary": summary
                                    }
                                })
                                break
                            except json.JSONDecodeError:
                                await websocket.send_json({
                                    "type": "message",
                                    "content": collector_output
                                })
                                break
                    
                    # Handle formatter_output
                    if isinstance(formatter_output, str):
                        json_match = re.search(r'\{.*\}', formatter_output, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            json_str = json_str.replace(r'\\$', '$')
                            financial_data = json.loads(json_str)
                            summary = formatter_output.replace(json_str, "").strip() or summary_output or "Financial data collected."
                        else:
                            json_str = formatter_output.replace(r'\\$', '$')
                            financial_data = json.loads(json_str)
                            summary = summary_output or "Financial data collected."
                    else:
                        financial_data = formatter_output
                        summary = summary_output or "Financial data collected."
                    
                    await websocket.send_json({
                        "type": "result",
                        "data": {
                            "financial_data": financial_data,
                            "summary": summary
                        }
                    })
                    break
                
                except (Exception, json.JSONDecodeError) as e:
                    retries += 1
                    if retries == MAX_RETRIES:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Failed after {MAX_RETRIES} attempts: {str(e)}"
                        })
                    else:
                        await websocket.send_json({
                            "type": "message",
                            "content": f"Retry attempt {retries + 1}/{MAX_RETRIES} due to error: {str(e)}"
                        })
                        await websocket.send_json({"type": "thinking", "status": True})
                        time.sleep(2)
            
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()