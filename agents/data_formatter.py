from crewai import Agent, Task, LLM
from groq import Groq
import os
from config import llm_client
from dotenv import load_dotenv

load_dotenv()

class DataFormatterAgent:
    def __init__(self):
        self.client = llm_client
        
        # Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.agent = Agent(
            role='Data Formatter',
            goal='Format financial data into a structured JSON response',
            backstory='Specialist in data structuring and presentation',
            verbose=True,
            llm=self.client
        )

    def create_task(self):
        return Task(
            description="Take the collected financial data and format it into a clean JSON structure suitable for frontend display",
            expected_output="A JSON object with the financial data formatted consistently, with all fields as strings or numbers suitable for display",
            agent=self.agent
        )