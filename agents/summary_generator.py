from crewai import Agent, Task, LLM
from groq import Groq
import os
from config import llm_client
from dotenv import load_dotenv

load_dotenv()

class SummaryGeneratorAgent:
    def __init__(self):
        self.client = llm_client
        
        # Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.agent = Agent(
            role='Summary Generator',
            goal='Generate a concise summary from financial data',
            backstory='Expert in financial analysis and summary creation',
            verbose=True,
            llm=self.client
        )

    def create_task(self):
        return Task(
            description="Generate a natural language summary of the financial data, highlighting key metrics and insights",
            expected_output="A string containing a concise, human-readable summary of the financial data",
            agent=self.agent
        )