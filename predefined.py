from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Predefined answers and their questions
predefined_answers = {
    "What we are doing?": """Impact Analytics delivers AI-native SaaS solutions and consulting services that help companies maximize profitability and customer satisfaction through deeper data insights and predictive analytics. 

    With a fully integrated, end-to-end platform for planning, forecasting, merchandising, pricing, and promotions, Impact Analytics empowers companies to make smarter decisions based on real-time insights, rather than relying on last year’s inputs to forecast and plan this year’s business.""",
    "How Agentic AI reshaping Retail industry?": """AI agents are redefining how businesses and individuals operate, innovate, and succeed. At the forefront of this technological revolution, our AI-native solutions empower you to achieve more with less effort. Partner with Impact Analytics and seize the opportunity to grow and stay ahead of your competition.""",
    "Why Impact Analytics?": """We are in the midst of a data revolution. Intelligent automation platforms are finally becoming affordable for businesses, but the Impact Analytics platform is the only one that does it all. Our cutting-edge AI solutions are complete, fully integrated, and built to boost revenues and profits.""",
    "Brief a bit about Pricesmart?": """AI-powered Impact Analytics PriceSmart™ uncovers underlying insights, the latest trends, price elasticities, competitor pricing, and more, driving the initial (or base), promotional, and markdown and clearance pricing decisions that maximize profitability.""",
    "Schedule a Consultation": "Thank you for showing your interest. Our team will reach you soon."
}

def unescape_single_quotes(str):
    """Unescape single quotes and other special characters to match predefined keys."""
    return str.replace("\\'", "'").replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')

@app.websocket("/ws")
async def websocket_predefined(websocket: WebSocket):
    await websocket.accept()
    logger.info("Predefined WebSocket (port 8001) connection opened")
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            logger.debug(f"Predefined WS (8001) received at {asyncio.get_event_loop().time()}: {data}")
            message_type = data.get("type")
            content = data.get("content")
            request_id = data.get("request_id", "unknown")
            await asyncio.sleep(0.6)

            # Send "thinking" message for predefined questions
            if message_type == "predefined_question":
                await websocket.send_json({"type": "thinking", "request_id": request_id})
                # Normalize the content to match predefined answers
                normalized_content = unescape_single_quotes(content)
                answer = predefined_answers.get(normalized_content, "No predefined answer available.")
                await asyncio.sleep(0.5)  # Minimal delay for realism
                logger.debug(f"Predefined WS (8001) sending message at {asyncio.get_event_loop().time()} for {request_id}")
                await websocket.send_json({"type": "message", "content": answer, "request_id": request_id})
            elif message_type == "fetch_predefined_questions":
                # Return the list of predefined questions (keys from predefined_answers)
                questions = list(predefined_answers.keys())
                await websocket.send_json({
                    "type": "predefined_questions",
                    "questions": questions,
                    "request_id": request_id
                })
            else:
                await websocket.send_json({"type": "error", "message": "Invalid message type", "request_id": request_id})
    except WebSocketDisconnect:
        logger.info("Predefined WebSocket (port 8001) client disconnected")
    except Exception as e:
        logger.error(f"Predefined WS (8001) error: {str(e)}")
        await websocket.send_json({"type": "error", "message": str(e), "request_id": "unknown"})