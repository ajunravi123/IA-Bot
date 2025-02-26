from crewai import Agent, Task
from config import llm_client
import os
from dotenv import load_dotenv

load_dotenv()

class DataFormatterAgent:
    def __init__(self):
        self.agent = Agent(
            role='Data Formatter',
            goal='Format financial data into a structured JSON response',
            backstory='Specialist in data structuring and presentation',
            verbose=True,
            llm=llm_client,
        )

    def create_task(self):
        return Task(
            description="Take the collected financial data and format it into a clean JSON structure containing only the following financial benefits: 'Margin_Rate_Lift', 'Margin_on_Revenue_Lift', 'Efficiency_Re_Investment', 'Reduction_in_Xfer_Expenses', 'Inventory_Carrying_Costs'. Each benefit should have 'low' and 'high' estimate values as calculated. Return only the JSON object with no additional text, nested keys (e.g., 'Action observational'), or explanations before or after the JSON. Ensure all values are in English.",
            expected_output="A JSON object with the financial benefits formatted as: {'Margin_Rate_Lift': {'low': value, 'high': value}, 'Margin_on_Revenue_Lift': {'low': value, 'high': value}, 'Efficiency_Re_Investment': {'low': value, 'high': value}, 'Reduction_in_Xfer_Expenses': {'low': value, 'high': value}, 'Inventory_Carrying_Costs': {'low': value, 'high': value}}",
            agent=self.agent
        )