# In agents/data_formatter.py
from crewai import Agent, Task
from config import llm_client
import os
from dotenv import load_dotenv

load_dotenv()

class DataFormatterAgent:
    def __init__(self):
        self.agent = Agent(
            role='Data Formatter',
            goal='Format collected financial data into a structured JSON response',
            backstory='Specialist in structuring financial data from various sources into a consistent format',
            verbose=True,
            llm=llm_client,
        )

    def create_task(self):
        return Task(
            description="Take the collected financial data from DataCollectorAgent and format it into a clean JSON structure containing only the following fields: 'company', 'analized_data_date', 'balance_sheet_inventory_cost', 'P&L_inventory_cost', 'Revenue', 'Headcount Old', 'Salary Average', 'gross_profit', 'gross_profit_percentage', 'market_cap', 'currency'. Ensure the output is a JSON object with these exact field names, preserving the values as provided (numbers or strings with units like '$200 million'), and include the 'currency' field to indicate the currency type of monetary amounts. Include only these fields with no additional text, markers (e.g., '**', '```json'), or calculations. If a field is missing or 'Not Available', retain it as 'Not Available' in the output.",
            expected_output="A JSON object with the financial data formatted as: {'company': value, 'analized_data_date': value, 'balance_sheet_inventory_cost': value, 'P&L_inventory_cost': value, 'Revenue': value, 'Headcount Old': value, 'Salary Average': value, 'gross_profit': value, 'gross_profit_percentage': value, 'market_cap': value, 'currency': value}",
            agent=self.agent
        )