from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from crewai import Crew, Process
from agents import DataCollectorAgent, DataFormatterAgent, SummaryGeneratorAgent
from tools import FinanceTools
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

finance_tools = FinanceTools()

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            company_input = data.strip()
            
            await websocket.send_json({"type": "thinking", "status": True})
            
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
            
            # Handle non-inventory case
            if isinstance(collector_output, str) and "inventory-based" in collector_output:
                await websocket.send_json({
                    "type": "message",
                    "content": collector_output
                })
            else:
                # Extract JSON from formatter_output if it’s mixed with text
                if isinstance(formatter_output, str):
                    # Use regex to find the JSON object (between { and })
                    json_match = re.search(r'\{.*\}', formatter_output, re.DOTALL)
                    if json_match:
                        try:
                            formatted_data = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            formatted_data = {"error": "Failed to parse formatter output as JSON"}
                    else:
                        formatted_data = {"error": "No valid JSON found in formatter output"}
                else:
                    formatted_data = formatter_output  # Assume it’s already a dict
                
                await websocket.send_json({
                    "type": "result",
                    "data": {
                        "formatted_data": formatted_data,
                        "summary": summary_output
                    }
                })
            
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        await websocket.close()