# In agents/benefit_calculator.py
from crewai import Agent, Task
from config import llm_client
import os
from dotenv import load_dotenv

load_dotenv()

class BenefitCalculatorAgent:
    def __init__(self):
        self.agent = Agent(
            role='Benefit Calculator',
            goal='Calculate financial benefits with low and high estimates based on collected financial data',
            backstory='Specialist in financial benefit calculations using predefined metrics',
            verbose=True,
            llm=llm_client,
        )

    def create_task(self, financial_data, finance_tools):
        return Task(
            description=f"""Take the collected financial data provided as input and use CalculatorTool to calculate the following financial benefits with low and high estimates in English:

                Input data: {financial_data}

                Calculate these benefits, organized by category:
                - "allocation_and_replenishment":
                    - "Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Efficiency Re-Investment": Low and high estimates in dollars, derived from 'Headcount Old' and 'Salary Average'.
                    - "Reduction in Xfer Expenses": Low and high estimates in dollars, derived from 'balance_sheet_inventory_cost'.
                    - "Inventory Carrying Costs": Low and high estimates in dollars, derived from 'balance_sheet_inventory_cost'.
                - "assortment_and_space":
                    - "Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Efficiency Re-Investment": Low and high estimates in dollars, derived from 'Headcount Old' and 'Salary Average'.
                    - "Reduction in Xfer Expenses": Low and high estimates in dollars, derived from 'balance_sheet_inventory_cost'.
                    - "Inventory Carrying Costs": Low and high estimates in dollars, derived from 'balance_sheet_inventory_cost'.
                - "merch_financial_planning":
                    - "Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Efficiency Re-Investment": Low and high estimates in dollars, derived from 'Headcount Old' and 'Salary Average'.
                    - "Inventory Carrying Costs": Low and high estimates in dollars, derived from 'balance_sheet_inventory_cost'.
                - "pricing":
                    - "Base - Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Base - Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Promo - Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Promo - Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "MD - Margin on Revenue Lift": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "MD - Margin Rate Lift (bps)": Low and high estimates in dollars, derived from 'Revenue', 'gross_profit', and 'gross_profit_percentage'.
                    - "Efficiency Re-Investment": Low and high estimates in dollars, derived from 'Headcount Old' and 'Salary Average'.

                Additionally, calculate the sum of all low and high estimates for each category under a 'sum' key.

                Return only a JSON object with the structure shown below. If any required data is missing or 'Not Available', CalculatorTool will handle it by returning 'Not Available' for the respective low/high values. Do not include additional text, markers, or explanations beyond the JSON object.""",
            expected_output="""A JSON object with calculated financial benefits and sums:
            {
                "benefits": {
                    "allocation_and_replenishment": {
                        "Margin Rate Lift (bps)": {"low": value, "high": value},
                        "Margin on Revenue Lift": {"low": value, "high": value},
                        "Efficiency Re-Investment": {"low": value, "high": value},
                        "Reduction in Xfer Expenses": {"low": value, "high": value},
                        "Inventory Carrying Costs": {"low": value, "high": value}
                    },
                    "assortment_and_space": {
                        "Margin Rate Lift (bps)": {"low": value, "high": value},
                        "Margin on Revenue Lift": {"low": value, "high": value},
                        "Efficiency Re-Investment": {"low": value, "high": value},
                        "Reduction in Xfer Expenses": {"low": value, "high": value},
                        "Inventory Carrying Costs": {"low": value, "high": value}
                    },
                    "merch_financial_planning": {
                        "Margin Rate Lift (bps)": {"low": value, "high": value},
                        "Margin on Revenue Lift": {"low": value, "high": value},
                        "Efficiency Re-Investment": {"low": value, "high": value},
                        "Inventory Carrying Costs": {"low": value, "high": value}
                    },
                    "pricing": {
                        "Base - Margin on Revenue Lift": {"low": value, "high": value},
                        "Base - Margin Rate Lift (bps)": {"low": value, "high": value},
                        "Promo - Margin on Revenue Lift": {"low": value, "high": value},
                        "Promo - Margin Rate Lift (bps)": {"low": value, "high": value},
                        "MD - Margin on Revenue Lift": {"low": value, "high": value},
                        "MD - Margin Rate Lift (bps)": {"low": value, "high": value},
                        "Efficiency Re-Investment": {"low": value, "high": value}
                    }
                },
                "sum": {
                    "allocation_and_replenishment": {"low": value, "high": value},
                    "assortment_and_space": {"low": value, "high": value},
                    "merch_financial_planning": {"low": value, "high": value},
                    "pricing": {"low": value, "high": value}
                }
            }""",
            agent=self.agent,
            tools=[finance_tools.calculator_tool]
        )