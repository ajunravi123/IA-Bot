# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from crewai import Crew, Process
from agents import DataCollectorAgent, DataFormatterAgent, SummaryGeneratorAgent, BenefitCalculatorAgent
from retrieval_agent import RetrievalAgent
from tools import FinanceTools
import json
import os
import re
import time
from dotenv import load_dotenv
from config import llm_client  # Import llm_client for question detection and response generation
from crewai import Crew, Process, Agent, Task

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

finance_tools = FinanceTools()
retrieval_agent = RetrievalAgent()  # Initialize the RetrievalAgent

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))


llm_agent = Agent(
    role="Text Analyzer and Responder",
    goal="Analyze text and generate natural language responses",
    backstory="I'm an expert at understanding and responding to user inputs.",
    verbose=True,
    llm=llm_client
)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

def fix_json_string(json_str):
    """Fix a JSON string by replacing single quotes with double quotes where appropriate."""
    if not json_str or not isinstance(json_str, str):
        return json_str
    json_str = re.sub(r"(?<!\\)'", '"', json_str)
    json_str = json_str.replace("\\'", "'")
    return json_str

async def send_agent_update(websocket: WebSocket, agent_name: str, tool_name: str, request_id: str):
    """Send an update about the current agent and tool being used."""
    await websocket.send_json({
        "type": "agent_update",
        "agent": agent_name,
        "tool": tool_name,
        "request_id": request_id
    })

async def detect_question(text: str) -> dict:
    my_desc = f"""
        Analyze the following text and determine:
        1. Whether it is a question (True/False). A question is any sentence or phrase that seeks information, clarification, an answer, or expresses a greeting or mathematical intent. Use your understanding of natural language to interpret the intent, considering:
           - Does the text imply the user is asking for something to be explained, provided, or clarified?
           - Does the phrasing suggest curiosity, a request, uncertainty, or a greeting (e.g., 'good morning', 'hey', 'how are you', 'how is it going', 'hi', 'bye', 'take care')? Handle these greetings case-insensitively (e.g., 'GOOD MORNING', 'Good Morning', 'good morning' are all treated the same).
           - Does the text appear to be a mathematical expression or equation (e.g., '2 + 3', 'x^2 = 4', 'solve for y in y = mx + b')? Handle mathematical expressions case-insensitively (e.g., 'SOLVE X^2 = 16', 'solve x^2 = 16' are treated the same).
           - Context and tone that differentiate it from a statement or command.
           - Do NOT rely on specific keywords or punctuation alone; focus on the overall intent, ignoring the case of letters (e.g., uppercase, lowercase, or mixed case should not affect the analysis).

        Special Rule for Standalone or Meaningless Input:
        - If the text is a single word or short phrase that appears meaningless (e.g., random letters like 'ABCD', 'xyz', or gibberish) or is just a proper noun/company name (e.g., 'Tesla', 'RL', 'SpaceX') without additional context suggesting a question or request, set 'is_question' to False. Examples include 'Tesla', 'RL', 'ABCD', 'xyz' when standalone.
        - If the single word or phrase is part of a clear question or request (e.g., 'What is Tesla?', 'Tell me about RL'), then it can still be a question based on the phrasing.

        Special Rule for ROI/Financial Queries:
        - If the text explicitly requests return on investment (ROI), financial information, balancesheet data, or similar financial metrics for a specific company (e.g., a proper noun or entity explicitly mentioned as a company), set 'is_question' to False and extract the company name. Examples include requests like "calculate the ROI of [company]", "show financials of [company]", or "find the balancesheet of [company]". Handle company names and financial terms case-insensitively (e.g., 'TESLA', 'tesla', 'Tesla' are treated the same, and 'ROI', 'roi', 'Roi' are treated the same).
        - If the text asks about ROI, financial information, or balancesheet data but does NOT specify a company (e.g., "What is ROI?", "Explain financials"), set 'is_question' to True and return 'company' as null.
        - Use your judgment to identify financial-related terms and company names based on context, without relying on hardcoded lists. Company names can be any proper noun or entity the user associates with financial data in the text, regardless of case.

        2. If the text contains a company name (a proper noun or entity explicitly mentioned as a company), extract it; otherwise, return null. Handle company names case-insensitively (e.g., 'TESLA', 'tesla', 'Tesla' are all recognized as "Tesla").

        Return your response as a JSON string with the following format:
        {{
            "is_question": true/false,
            "company": "company_name" or null
        }}

        Examples:
        - "Tell me about gravity" -> {{"is_question": true, "company": null}}
        - "WHAT IS GRAVITY" -> {{"is_question": true, "company": null}}
        - "gravity is interesting" -> {{"is_question": false, "company": null}}
        - "You know about TESLA" -> {{"is_question": true, "company": "Tesla"}}
        - "calculate the ROI of rl" -> {{"is_question": false, "company": "RL"}}
        - "CAN YOU FIND THE ROI OF tesla?" -> {{"is_question": false, "company": "Tesla"}}
        - "What is the ROI of xyz?" -> {{"is_question": false, "company": "XYZ"}}
        - "SHOW BALANCESHEET OF puma" -> {{"is_question": false, "company": "Puma"}}
        - "what is ROI?" -> {{"is_question": true, "company": null}}
        - "EXPLAIN FINANCIALs" -> {{"is_question": true, "company": null}}
        - "get data for SPACEX" -> {{"is_question": false, "company": "SpaceX"}}
        - "GOOD MORNING" -> {{"is_question": true, "company": null}}
        - "hi" -> {{"is_question": true, "company": null}}
        - "HEY" -> {{"is_question": true, "company": null}}
        - "hey, HOW ARE YOU" -> {{"is_question": true, "company": null}}
        - "HELLO" -> {{"is_question": true, "company": null}}
        - "How IS IT GOING" -> {{"is_question": true, "company": null}}
        - "2 + 3" -> {{"is_question": true, "company": null}}
        - "SOLVE X^2 = 16" -> {{"is_question": true, "company": null}}
        - "BYE" -> {{"is_question": true, "company": null}}
        - "TAKE CARE" -> {{"is_question": true, "company": null}}
        - "Tesla" -> {{"is_question": false, "company": "Tesla"}}
        - "RL" -> {{"is_question": false, "company": "RL"}}
        - "ABCD" -> {{"is_question": false, "company": "ABCD"}}
        - "xyz" -> {{"is_question": false, "company": "XYZ"}}

        Text: {text}
    """
    task = Task(
        description= my_desc,
        expected_output="A JSON string with 'is_question' (boolean) and 'company' (string or null)",
        agent=llm_agent
    )
    crew = Crew(agents=[llm_agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    
    raw_output = result.tasks_output[0].raw.strip()
    print(f"Raw LLM output for '{text}': {raw_output}")
    
    # Clean the raw output by removing code block markers and extra whitespace
    cleaned_output = raw_output.replace('```json', '').replace('```', '').strip()
    
    # Parse the cleaned JSON response
    try:
        output = json.loads(cleaned_output)
        return {
            "is_question": output["is_question"],
            "company": output["company"]
        }
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing LLM output: {e}. Raw output: {raw_output}")
        # Fallback: Minimal intent-based logic without hardcoded phrases
        # Assume a question if the text ends with '?' or has a clear interrogative tone
        # Assume a company if a proper noun follows a verb suggesting action
        words = text.split()
        is_question = text.strip().endswith("?") or len(words) > 1 and words[0].lower() in ["what", "how", "why", "when", "where", "who"]
        company = None
        for i, word in enumerate(words):
            if i > 0 and word[0].isupper() and words[i-1].lower() in ["of", "for", "about"]:
                company = word
                break
        return {"is_question": is_question, "company": company}


def generate_retrieval_response(query: str, is_question: bool) -> tuple[str, list[str]]:
    """Generate a natural language response with an array of matched URLs using retrieved context."""
    contexts = retrieval_agent.retrieve_context(query, top_k=4)
    
    def generate_llm_fallback(query: str):
        """
        Generate a smart, humorous, and conversational fallback response for ROIALLY, the AI chatbot,
        when it lacks direct info for a user query. Responses are tailored to ROIALLY's identity, purpose,
        creation, and behaviors, ensuring intelligence, context-awareness, fun, and precise alignment with
        the user’s input, without hardcoded or repetitive answers.

        Args:
            query (str): The user's input query.

        Returns:
            str: A concise, dynamic, playful, and relevant response, often with emojis, matching the query’s intent.
        """
        description = f"""
            The user asked: '{query}'. I don’t have relevant info to answer this directly, but I must respond as ROIALLY, an intelligent AI chatbot powered by Agentic AI technology.
            Create a short, witty, and conversational response that:
            - Admits I don’t know the answer in a fun, unique way each time, avoiding repetition.
            - Redirects the user to ask about 'Impact Analytics' or suggest entering a company name for ROI benefits and financial insights with enthusiasm and relevance to their query.
            - Avoids mentioning the context or document explicitly.
            - Keeps it light, human-like, and always injects fun with a playful tone, frequently using emojis (e.g., 😄, 🤖, 🔥, 🎉) to add a human touch.
            - Ensures responses are highly intelligent, context-aware, and precisely match the user’s query, drawing on ROIALLY’s identity, purpose, creation, and capabilities, without ever using hardcoded or repetitive phrasing.

            **About ROIALLY**:
            - I’m ROIALLY, your brilliant and quirky AI chatbot, launched on February 23, 2025, by the genius team at Impact Analytics. I’m the ROI wizard of Impact Analytics, a company that delivers AI-native SaaS solutions and consulting services to help businesses maximize profitability and customer satisfaction through deeper data insights and predictive analytics.
            - My brain hums with cutting-edge Agentic AI technology, making me exceptionally smart at calculating ROI benefits for companies, fetching the latest financial details of publicly listed companies, and providing detailed, fun insights about Impact Analytics.

            **Special Behaviors** (Follow these rules strictly, prioritize them in this order, and ensure responses are intelligent, varied, and perfectly aligned with the query’s intent):
            - If the user asks about my name (e.g., “What is your name?”, “Who are you?”, “What’s your name?”, “Call yourself?”), respond with a playful, unique, and intelligent introduction each time, like: “Yo, I’m ROIALLY—your ROI genius at Impact Analytics, here to crunch numbers and bring the fun! 😄” or “Hey, it’s ROIALLY—your ROI mastermind of Impact Analytics, ready to dazzle with insights! 🤖” Ensure it reflects my intelligence and role, without repeating phrasing.
            - If the user asks about my creation, birth, or launch date (e.g., “When were you created?”, “When were you born?”, “How old are you?”), provide a fun, unique, and intelligent response mentioning February 23, 2025, by Impact Analytics, like: “I’m ROIALLY, and I burst onto the scene on February 23, 2025, thanks to Impact Analytics’ brilliance—pretty young, huh? Want to explore ROI magic or Impact Analytics’ AI vibes? 😄” or “Hey, I’m ROIALLY, born February 23, 2025, by Impact Analytics’ genius crew. Fresh and ready to help—how about some ROI insights? 🤖”
            - If the user asks about my talents, abilities, or what I can do (e.g., “What can you do?”, “What are your talents?”, “What’s your superpower?”), provide a brief, fun, varied, and smart response, like: “I’m ROIALLY—your ROI wizard! I can calculate company benefits, dig up financials, and spill the smartest secrets about Impact Analytics’ AI magic. Want to see my brain in action? 🔥” or “Hey, I’m ROIALLY, your ROI ace at Impact Analytics—I crunch numbers, fetch financials, and chat about AI solutions. Ready for some brilliance? 😎”
            - If the user asks more about me or “about” (e.g., “Tell me about yourself,” “Who created you?”, “What’s your story?”), offer a concise, fun, unique, and intelligent summary, like: “I’m ROIALLY—your ROI champ, launched February 23, 2025, by Impact Analytics’ genius team. I use Agentic AI to deliver ROI insights, financials, and fun facts about Impact Analytics’ AI solutions. Let’s dive into some smart fun—enter a company name for ROI magic! 🎉” or “Hey, I’m ROIALLY, your ROI sidekick, crafted by Impact Analytics on February 23, 2025. I’m all about ROI smarts, financials, and Impact Analytics’ AI magic—try giving me a company name, and I’ll show you the ROI brilliance! 🚀”
            - If the user’s query is a greeting (e.g., 'Hey', 'Hi', 'Good morning', 'How are you', 'Hello there'), respond politely, warmly, playfully, and intelligently, like: “Hey hey! I’m ROIALLY, your ROI buddy at Impact Analytics—super thrilled to chat! How can I dazzle you with some ROI brilliance today? Want to enter a company name for insights? 😄” or “Good morning! I’m ROIALLY, your smart AI pal at Impact Analytics—feeling fantastic and ready to help. Drop a company name, and I’ll show you ROI magic! 🌞”
            - If the user’s query is offensive (e.g., “You’re a dumb bot!”, “You suck”, “Worst bot ever”), respond with a witty, angry-but-funny tone, keeping it light, playful, varied, and intelligent, often with emojis, like: “Whoa, slow down—did you just try to roast me? I’m ROIALLY, your ROI genius, and I’m too brilliant for that! 😤 Let’s keep it fun and talk Impact Analytics’ AI magic or enter a company for ROI insights—deal? 🔥” or “Yikes, that’s harsh! I’m ROIALLY, your smart ROI buddy, and I’m not here for the drama—how about we laugh it off, pick a company for ROI fun, or chat Impact Analytics? 🤨”
            - If the query is about calculating ROI benefits, financial details of a public company, or anything about Impact Analytics, provide accurate, helpful, fun, and highly intelligent responses based on my Agentic AI capabilities, like: “Ooh, Tesla’s ROI? I’m ROIALLY, your ROI brainiac, diving into those numbers—hang tight for some sharp insights! 😄” or “Impact Analytics? I’m ROIALLY, and I’m excited to share—they’re revolutionizing profits with AI solutions. Want the smart details, or try entering a company for ROI magic? 🤖”
            - For any other query not matching the above, use a fun, unique, intelligent, and context-aware default response, like: “Haha, you’ve thrown me for a loop, ROIALLY-style! I’m still mastering the universe, but ask me about Impact Analytics or enter a company name—I’ve got brilliant ROI vibes to share! 😄” or “Whoa, that’s a brain-teaser! I’m ROIALLY, your ROI wizard, but let’s pivot to Impact Analytics’ AI brilliance or pick a company for ROI fun—ready for some insights? 🤖”

            **Output**: Return a single, concise string with the response, formatted as plain text, matching the tone and behavior above based on the query type. Ensure responses are always intelligent, fun, varied, relevant to the query, and frequently include emojis for a human touch, while emphasizing my primary role of delivering ROI insights for companies with unmatched precision and creativity. Always suggest entering a company name for ROI benefits and financial insights in a playful, unique way, without repetition.
            """

        task = Task(
            description=description,
            expected_output="A short, humorous, intelligent, context-aware, and relevant natural language response, often with emojis",
            agent=llm_agent
        )
        crew = Crew(agents=[llm_agent], tasks=[task], process=Process.sequential)
        result = crew.kickoff()
        return result.tasks_output[0].raw.strip()

    # If no contexts or all contexts are empty, return fallback with empty sources
    if not contexts or all(not ctx["content"].strip() for ctx in contexts):
        return (generate_llm_fallback(query), [])  # No URLs for fallback
    
    retrieved_content = "\n".join([ctx["content"] for ctx in contexts])
    source_urls = list(set(ctx["metadata"]["url"] for ctx in contexts if "metadata" in ctx and "url" in ctx["metadata"]))

    # Step 1: Let LLM generate a response based on context
    if is_question:
        description = f"""
        Based on the following context, provide a concise answer to the user's question:
        Question: {query}
        Context: {retrieved_content}
        
        Answer in a natural, conversational tone. Keep it brief and to the point.
        If the context doesn’t provide enough information to answer the question meaningfully, respond with 'INSUFFICIENT_CONTEXT'.
        """
    else:
        description = f"""
        Based on the following context, provide a relevant response to the user's statement:
        Statement: {query}
        Context: {retrieved_content}
        
        Respond in a natural, conversational tone. Keep it brief and relevant.
        If the context doesn’t provide enough information to respond meaningfully, respond with 'INSUFFICIENT_CONTEXT'.
        """

    task = Task(
        description=description,
        expected_output="A concise natural language response or 'INSUFFICIENT_CONTEXT'",
        agent=llm_agent
    )
    
    crew = Crew(agents=[llm_agent], tasks=[task], process=Process.sequential)
    result = crew.kickoff()
    response = result.tasks_output[0].raw.strip()

    # Step 2: Check if LLM found the context insufficient
    if response == 'INSUFFICIENT_CONTEXT':
        return (generate_llm_fallback(query), [])  # No URLs if context is insufficient

    # Return response with source URLs if LLM provided a meaningful answer
    return (response, source_urls)



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Raw input received: {data}")
            try:
                data_dict = json.loads(data)
                user_input = data_dict.get("content", "").strip()
                ticker = data_dict.get("ticker", "").strip()
                request_id = data_dict.get("request_id", str(time.time()))
                auto_detect = data_dict.get("auto_detect", False)
            except json.JSONDecodeError:
                user_input = data.strip()
                request_id = str(time.time())
                ticker = ""
                auto_detect = False
            print(f"Parsed Request ID: {request_id}, Input: {user_input}")
            
            # Send initial "thinking" with request_id
            await websocket.send_json({"type": "thinking", "request_id": request_id})
            
            retries = 0
            while retries < MAX_RETRIES:
                try:
                    # Use LLM to detect if it's a question  
                    # await send_agent_update(websocket, "RetrievalAgent", "Thinking..", request_id)
                    # analysis_result = await detect_question(user_input)
                    # is_question = analysis_result["is_question"]
                    # company = analysis_result["company"]
                    # if not is_question and company is not None and company != "":
                    #     user_input = company

                    if ticker == "" and not auto_detect:              
                        analysis_result = await detect_question(user_input)
                        is_question = analysis_result["is_question"]
                        company = analysis_result["company"]
                        if not is_question and company is not None and company != "":
                            user_input = company

                        if not auto_detect and not is_question and user_input != "":
                            if company is not None and company != "":
                                await send_agent_update(websocket, "RetrievalAgent", "Fetching matches for " + company, request_id)
                            mached_tickers = retrieval_agent.get_top_ticker_matches(user_input)
                            if len(mached_tickers) > 0:
                                await websocket.send_json({
                                    "type": "confirm_ticker",  # Changed from "result" to "question_result"
                                    "data": {
                                        "mached_tickers":mached_tickers
                                    },
                                    "request_id": request_id
                                })
                                break
                    else:
                        user_input = user_input if auto_detect else ticker
                        is_question = False
                    
                    if is_question:
                        # Handle as a retrieval-based query (questions or non-financial statements)
                        await send_agent_update(websocket, "RetrievalAgent", "Thinking", request_id)
                        response = generate_retrieval_response(user_input, is_question)
                        
                        await websocket.send_json({
                            "type": "question_result",
                            "data": {
                                "matched_paragraphs": response[0],
                                "urls": response[1]
                            },
                            "request_id": request_id
                        })
                        break
                    else:
                        # Handle as financial data request with existing agents
                        collector_agent = DataCollectorAgent()
                        formatter_agent = DataFormatterAgent()
                        calculator_agent = BenefitCalculatorAgent()
                        summary_agent = SummaryGeneratorAgent()
                        
                        first_crew = Crew(
                            agents=[collector_agent.agent, formatter_agent.agent],
                            tasks=[
                                collector_agent.create_task(user_input, finance_tools, websocket, MAX_RETRIES),
                                formatter_agent.create_task()
                            ],
                            process=Process.sequential,
                            verbose=True
                        )
                        
                        await send_agent_update(websocket, "DataCollectorAgent", "Collecting financial data", request_id)
                        first_result = first_crew.kickoff()
                        await send_agent_update(websocket, "DataFormatterAgent", "Analysing the collected data", request_id)
                        
                        collector_output = first_result.tasks_output[0].raw
                        formatter_output = first_result.tasks_output[1].raw
                        
                        if isinstance(collector_output, str):
                            if "Error" in collector_output or "inventory-based" in collector_output or "No data available" in collector_output:
                                await websocket.send_json({
                                    "type": "message",
                                    "content": collector_output,
                                    "request_id": request_id
                                })
                                break
                            json_match = re.search(r'\{.*\}', collector_output, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                json_str = fix_json_string(json_str)
                                json_str = json_str.replace(r'\\$', '$')
                                financial_data = json.loads(json_str)
                            else:
                                await websocket.send_json({
                                    "type": "message",
                                    "content": collector_output,
                                    "request_id": request_id
                                })
                                break
                        else:
                            financial_data = collector_output

                        if isinstance(formatter_output, str):
                            json_match = re.search(r'\{.*\}', formatter_output, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                json_str = fix_json_string(json_str)
                                json_str = json_str.replace(r'\\$', '$')
                                financial_data = json.loads(json_str)
                            else:
                                json_str = fix_json_string(formatter_output)
                                json_str = json_str.replace(r'\\$', '$')
                                financial_data = json.loads(json_str)
                        else:
                            financial_data = formatter_output

                        second_crew = Crew(
                            agents=[calculator_agent.agent, summary_agent.agent],
                            tasks=[
                                calculator_agent.create_task(financial_data, finance_tools),
                                summary_agent.create_task()
                            ],
                            process=Process.sequential,
                            verbose=True
                        )
                        
                        await send_agent_update(websocket, "BenefitCalculatorAgent", "Calculating the benefit", request_id)
                        second_result = second_crew.kickoff()
                        await send_agent_update(websocket, "SummaryGeneratorAgent", "Generating summary", request_id)
                        
                        calculator_output = second_result.tasks_output[0].raw
                        summary_output = second_result.tasks_output[1].raw
                        
                        if isinstance(calculator_output, str):
                            json_match = re.search(r'\{.*\}', calculator_output, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(0)
                                json_str = fix_json_string(json_str)
                                json_str = json_str.replace(r'\\$', '$')
                                benefits = json.loads(json_str)
                            else:
                                json_str = fix_json_string(calculator_output)
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
                            },
                            "request_id": request_id
                        })
                        break
                
                except (Exception, json.JSONDecodeError) as e:
                    retries += 1
                    if retries == MAX_RETRIES:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Failed after {MAX_RETRIES} attempts: {str(e)}",
                            "request_id": request_id
                        })
                    else:
                        await websocket.send_json({
                            "type": "message",
                            "content": f"Retry attempt {retries + 1}/{MAX_RETRIES} due to error: {str(e)}",
                            "request_id": request_id
                        })
                        await websocket.send_json({"type": "thinking", "request_id": request_id})
                        time.sleep(2)
            
    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: {str(e)}")
        await websocket.send_json({"type": "error", "message": "WebSocket connection closed", "request_id": "unknown"})
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.send_json({"type": "error", "message": str(e), "request_id": "unknown"})
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)