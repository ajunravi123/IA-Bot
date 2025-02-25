from crewai import Agent, Task
from config import llm_client
import os
from dotenv import load_dotenv

load_dotenv()

class DataCollectorAgent:
    def __init__(self):
        self.agent = Agent(
            role='Financial Data Collector',
            goal='Collect comprehensive financial data for inventory-based companies',
            backstory='Expert in financial analysis and data collection from multiple sources, specializing in inventory-based companies',
            verbose=True,
            llm=llm_client,
            memory=True
        )

    def create_task(self, company_input, finance_tools, websocket):
        async def collect_missing_data(task_output):
            required_fields = [
                "company_name", "analyzed_data_date", "balance_sheet_inventory_cost",
                "P&L_inventory_cost", "Revenue", "Headcount Old", "Efficiency Output High",
                "Efficiency Output Low", "Salary Average", "gross_profit",
                "gross_profit_percentage", "market_cap"
            ]
            
            if isinstance(task_output, str):
                return task_output
            
            if isinstance(task_output, dict):
                missing_items = [field for field in required_fields if field not in task_output or task_output[field] is None]
                if missing_items:
                    await websocket.send_json({
                        "type": "question",
                        "message": f"I couldn't find some data for {company_input}. Could you please provide: {', '.join(missing_items)}?"
                    })
                    response = await websocket.receive_text()
                    user_values = response.split(',')
                    for field, value in zip(missing_items, user_values):
                        task_output[field] = value.strip()
                return task_output
            
            return {"error": "Unexpected task output format"}

        return Task(
            description=f"""Process the input '{company_input}' to collect financial data for an inventory-based company. Follow these steps:

            1. **Identify Input Type**: Determine if '{company_input}' is a ticker symbol (1-5 uppercase letters, e.g., 'AAPL') or a company name (e.g., 'Apple Inc.'). Use TickerLookupTool if it’s a company name to find its ticker symbol. If the ticker cannot be found, return: "Error: Could not determine ticker for '{company_input}'."

            2. **Verify Inventory Status**: Using the ticker from step 1, check if the company is inventory-based with InventoryCompanyChecker. A company is inventory-based if it has significant inventory on its balance sheet or operates in sectors like consumer goods, industrial, retail, or manufacturing. If not inventory-based, return: "This application is designed for inventory-based companies only. '{company_input}' does not appear to be inventory-based."

            3. **Collect Financial Data**: If the company is inventory-based, gather data in JSON format with these exact fields:
            - "company_name": Full name of the company (string).
            - "analyzed_data_date": Current date in 'YYYY-MM-DD' format (string).
            - "balance_sheet_inventory_cost": Inventory value from balance sheet (number or string, e.g., '200 million').
            - "P&L_inventory_cost": Cost of revenue from profit & loss statement (number or string, e.g., '$329.5 million').
            - "Revenue": Total revenue (number or string, e.g., '$133.7 billion').
            - "Headcount": Number of employees (number or string, e.g., '164,274').
            - "Efficiency Output High": Highest efficiency metric, if available (number or string, e.g., '500').
            - "Efficiency Output Low": Lowest efficiency metric, if available (number or string, e.g., '100').
            - "Salary Average": Average employee salary (number or string, e.g., '$60,000').
            - "gross_profit": Gross profit (number or string, e.g., '$98.74 million').
            - "gross_profit_percentage": Gross profit as a percentage of revenue (number, e.g., 20.5).
            - "market_cap": Market capitalization (number or string, e.g., '$850 billion').
            Values can be numbers or strings with units (e.g., '$200 million', '300 billion').

            4. **Handle Missing Data**: If any fields are missing or unavailable from the tools, use the callback to prompt the user for those specific values.

            **Available Tools**:
            - **TickerLookupTool**: Converts a company name to its ticker symbol.
            - **YahooFinanceDataFetcher**: Retrieves financial data from Yahoo Finance using the ticker.
            - **AlphaVantageDataFetcher**: Retrieves financial data from Alpha Vantage using the ticker.
            - **InventoryCompanyChecker**: Determines if the company is inventory-based using the ticker.

            **Output**: Return a JSON object with all specified fields if the company is inventory-based, or a string error message if not inventory-based or if the ticker cannot be determined.""",
            expected_output="A JSON object containing the requested financial data if the company is inventory-based, or a string message if it’s not.",
            agent=self.agent,
            tools=[
                finance_tools.ticker_lookup_tool,  
                finance_tools.yfinance_tool,
                finance_tools.alpha_vantage_tool,
                finance_tools.inventory_check_tool, 
                # finance_tools.search_company_tool,  
                # finance_tools.file_read_tool,       
            ],
            callback=collect_missing_data
        )