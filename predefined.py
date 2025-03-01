from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Predefined answers
predefined_answers = {
    "What is the market cap of Tesla?": "Tesla's market cap is approximately $1 trillion as of early 2025.",
    "How does Apple's revenue compare to last year?": "Apple's revenue grew by 5% compared to last year, reaching $394 billion.",
    "What are the latest financials for Microsoft?": "Microsoft reported revenue of $62 billion in its latest quarter, with a net income of $22 billion.",
    "Can you analyze Amazon's gross profit?": "Amazon's gross profit for the latest period was $75 billion, up 10% year-over-year.",
    "What is the headcount of Google?": "Google's headcount is around 180,000 employees as of 2025."
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

            # Unescape the content to match predefined answers
            normalized_content = unescape_single_quotes(content)

            # Send "thinking" message
            await websocket.send_json({"type": "thinking", "request_id": request_id})

            if message_type == "predefined_question":
                # Fast response for predefined questions
                answer = predefined_answers.get(normalized_content, "No predefined answer available.")
                await asyncio.sleep(0.5)  # Minimal delay for realism
                logger.debug(f"Predefined WS (8001) sending message at {asyncio.get_event_loop().time()} for {request_id}")
                await websocket.send_json({"type": "message", "content": answer, "request_id": request_id})
            else:
                await websocket.send_json({"type": "error", "message": "Invalid message type", "request_id": request_id})
    except WebSocketDisconnect:
        logger.info("Predefined WebSocket (port 8001) client disconnected")
    except Exception as e:
        logger.error(f"Predefined WS (8001) error: {str(e)}")
        await websocket.send_json({"type": "error", "message": str(e), "request_id": "unknown"})