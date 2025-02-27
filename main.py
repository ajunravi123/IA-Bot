from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from crewai import Crew, Process
from agents import DataCollectorAgent, DataFormatterAgent, SummaryGeneratorAgent, BenefitCalculatorAgent
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

def fix_json_string(json_str):
    """Fix a JSON string by replacing single quotes with double quotes where appropriate."""
    if not json_str or not isinstance(json_str, str):
        return json_str
    # Replace single quotes with double quotes, but preserve single quotes within values
    json_str = re.sub(r"(?<!\\)'", '"', json_str)
    # Remove any escaped single quotes that shouldn’t be there
    json_str = json_str.replace("\\'", "'")
    return json_str

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
                    calculator_agent = BenefitCalculatorAgent()
                    summary_agent = SummaryGeneratorAgent()
                    
                    # First Crew: Collect and format financial data
                    first_crew = Crew(
                        agents=[collector_agent.agent, formatter_agent.agent],
                        tasks=[
                            collector_agent.create_task(company_input, finance_tools, websocket, MAX_RETRIES),
                            formatter_agent.create_task()
                        ],
                        process=Process.sequential,
                        verbose=True
                    )
                    
                    first_result = first_crew.kickoff()
                    
                    collector_output = first_result.tasks_output[0].raw
                    formatter_output = first_result.tasks_output[1].raw
                    
                    if isinstance(collector_output, str):
                        if "Error" in collector_output or "inventory-based" in collector_output or "No data available" in collector_output:
                            await websocket.send_json({
                                "type": "message",
                                "content": collector_output
                            })
                            break
                        json_match = re.search(r'\{.*\}', collector_output, re.DOTALL)
                        if json_match:
                            try:
                                json_str = json_match.group(0)
                                json_str = fix_json_string(json_str)  # Fix single quotes
                                json_str = json_str.replace(r'\\$', '$')
                                financial_data = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                print(f"Failed to parse collector_output: {collector_output}, Error: {e}")
                                await websocket.send_json({
                                    "type": "message",
                                    "content": f"Error parsing financial data: {collector_output}"
                                })
                                break
                        else:
                            await websocket.send_json({
                                "type": "message",
                                "content": collector_output
                            })
                            break
                    else:
                        financial_data = collector_output

                    if isinstance(formatter_output, str):
                        json_match = re.search(r'\{.*\}', formatter_output, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            json_str = fix_json_string(json_str)  # Fix single quotes
                            json_str = json_str.replace(r'\\$', '$')
                            financial_data = json.loads(json_str)
                        else:
                            json_str = fix_json_string(formatter_output)  # Fix single quotes
                            json_str = json_str.replace(r'\\$', '$')
                            financial_data = json.loads(json_str)
                    else:
                        financial_data = formatter_output

                    # Second Crew: Calculate benefits and generate summary
                    second_crew = Crew(
                        agents=[calculator_agent.agent, summary_agent.agent],
                        tasks=[
                            calculator_agent.create_task(financial_data, finance_tools),
                            summary_agent.create_task()
                        ],
                        process=Process.sequential,
                        verbose=True
                    )
                    
                    second_result = second_crew.kickoff()
                    
                    calculator_output = second_result.tasks_output[0].raw
                    summary_output = second_result.tasks_output[1].raw
                    
                    if isinstance(calculator_output, str):
                        json_match = re.search(r'\{.*\}', calculator_output, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            json_str = fix_json_string(json_str)  # Fix single quotes
                            json_str = json_str.replace(r'\\$', '$')
                            benefits = json.loads(json_str)
                        else:
                            json_str = fix_json_string(calculator_output)  # Fix single quotes
                            json_str = json_str.replace(r'\\$', '$')
                            benefits = json.loads(json_str)
                    else:
                        benefits = calculator_output

                    summary = summary_output or "Financial data and benefits calculated."
                    
                    await websocket.send_json({
                        "type": "result",
                        "data": {
                            "financial_data": financial_data,
                            "benefits": benefits,
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