# In agents/data_collector.py
from config import llm_client
from crewai import Agent, Task
import os
from dotenv import load_dotenv

load_dotenv()

MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))


class DataCollectorAgent:
    def __init__(self):
        self.agent = Agent(
            role='Financial Data Collector',
            goal='Collect financial data and calculate benefits for inventory-based companies',
            backstory='Expert in financial analysis and data collection from Yahoo Finance and Alpha Vantage, specializing in inventory-based companies',
            verbose=True,
            llm=llm_client,
            memory=True
        )

    def create_task(self, company_input, finance_tools, websocket, max_retries=MAX_RETRIES):
        async def collect_missing_data(task_output, attempt=1):
            required_fields = [
                "Revenue",              # For all benefits
                "gross_profit",         # For Margin_Rate_Lift, Margin_on_Revenue_Lift
                "gross_profit_percentage",  # For Margin_Rate_Lift, Margin_on_Revenue_Lift
                "Headcount",            # For Efficiency_Re_Investment
                "Salary Average",       # For Efficiency_Re_Investment
                "balance_sheet_inventory_cost"  # For Reduction_in_Xfer_Expenses, Inventory_Carrying_Costs
            ]
            
            # Handle None or empty response from LLM
            if task_output is None or (isinstance(task_output, str) and not task_output.strip()):
                if attempt < max_retries:
                    await websocket.send_json({
                        "type": "message",
                        "content": f"Attempt {attempt}/{max_retries}: No data collected for '{company_input}'. Retrying..."
                    })
                    await websocket.send_json({"type": "thinking", "status": True})
                    # Retry the task by creating a new one
                    new_task = Task(
                        description=description,
                        expected_output="A JSON object with calculated financial benefits derived from actual fetched data if the company is inventory-based, or a string error message if it’s not.",
                        agent=self.agent,
                        tools=[
                            finance_tools.ticker_lookup_tool,
                            finance_tools.yfinance_tool,
                            finance_tools.alpha_vantage_tool,
                            finance_tools.inventory_check_tool,
                            finance_tools.calculator_tool
                        ],
                        callback=lambda output: collect_missing_data(output, attempt + 1)
                    )
                    return await new_task.execute()
                return {"error": f"Failed to collect data for '{company_input}' after {max_retries} attempts - received None or empty output"}
            
            # Handle error messages
            if isinstance(task_output, str):
                if "Error" in task_output or "inventory-based" in task_output:
                    return task_output
            
            # Process collected data
            if isinstance(task_output, dict):
                missing_items = [field for field in required_fields if field not in task_output or task_output[field] is None or task_output[field] == "Not Available"]
                if missing_items:
                    if attempt < max_retries:
                        await websocket.send_json({
                            "type": "message",
                            "content": f"Attempt {attempt}/{max_retries}: Insufficient data for '{company_input}' (missing: {', '.join(missing_items)}). Retrying..."
                        })
                        await websocket.send_json({"type": "thinking", "status": True})
                        # Retry the task
                        new_task = Task(
                            description=description,
                            expected_output="A JSON object with calculated financial benefits derived from actual fetched data if the company is inventory-based, or a string error message if it’s not.",
                            agent=self.agent,
                            tools=[
                                finance_tools.ticker_lookup_tool,
                                finance_tools.yfinance_tool,
                                finance_tools.alpha_vantage_tool,
                                finance_tools.inventory_check_tool,
                                finance_tools.calculator_tool
                            ],
                            callback=lambda output: collect_missing_data(output, attempt + 1)
                        )
                        return await new_task.execute()
                    else:
                        # Prompt user for missing data on final attempt
                        await websocket.send_json({
                            "type": "question",
                            "message": f"After {max_retries} attempts, I couldn't find some data for '{company_input}'. Please provide: {', '.join(missing_items)}"
                        })
                        response = await websocket.receive_text()
                        user_values = response.split(',')
                        for field, value in zip(missing_items, user_values):
                            task_output[field] = value.strip()
                
                # Calculate benefits with collected data
                benefits = finance_tools.calculator_tool._run(task_output)
                
                # Generate summary based on calculated benefits
                summary_parts = []
                for key, value in benefits.items():
                    if isinstance(value, dict) and "low" in value and "high" in value:
                        if value["low"] != "Not Available" and value["high"] != "Not Available":
                            summary_parts.append(f"{key.replace('_', ' ')} ranges from {value['low']} to {value['high']}.")
                        else:
                            summary_parts.append(f"{key.replace('_', ' ')} could not be calculated due to missing data.")
                    else:
                        summary_parts.append(f"{key.replace('_', ' ')} could not be calculated due to missing data.")
                summary = " ".join(summary_parts) if summary_parts else "No benefits could be calculated due to insufficient data."
                
                return {
                    "benefits": benefits,
                    "summary": summary
                }
            
            return {"error": f"Unexpected task output format for '{company_input}' after {attempt} attempts - received: {task_output}"}

        description = (
            "Process the input '" + company_input + "' to collect financial data and calculate benefits for an inventory-based company in English only. Follow these steps:\n\n"
            "1. **Find Ticker Symbol**: Use TickerLookupTool to determine the ticker symbol for '" + company_input + "'. If '" + company_input + "' is a ticker (1-5 uppercase letters, e.g., 'AAPL'), validate it. If it’s a company name (e.g., 'Tesla Inc.'), find its ticker. The tool will return a string like \"This is the ticker for '" + company_input + "': [ticker]\" (e.g., \"This is the ticker for 'Tesla Inc.': TSLA\"). Extract the ticker symbol (e.g., 'TSLA') from the response. If an error occurs, return only the error message from the tool (e.g., \"Error: No ticker found for '" + company_input + "'\") and stop processing.\n\n"
            "2. **Verify Inventory Status**: Use InventoryCompanyChecker with the ticker from step 1 to confirm the company is inventory-based (has significant inventory on its balance sheet or operates in sectors like consumer goods, industrial, retail, or manufacturing). If not inventory-based, return only the string: \"This application is designed for inventory-based companies only. '" + company_input + "' does not appear to be inventory-based\" and stop processing.\n\n"
            "3. **Collect Financial Data**: If the company is inventory-based, gather data in JSON format with these required fields in English, using YahooFinanceDataFetcher as the primary source and AlphaVantageDataFetcher to supplement missing data:\n"
            "   - \"Revenue\": Total revenue from Yahoo Finance 'Total Revenue' or Alpha Vantage 'RevenueTTM' (e.g., '$133.7 billion' or number).\n"
            "   - \"gross_profit\": Gross profit from Yahoo Finance 'Gross Profit' or Alpha Vantage 'GrossProfitTTM' (e.g., '$98.74 million' or number).\n"
            "   - \"gross_profit_percentage\": Gross profit as percentage of revenue from Yahoo Finance or Alpha Vantage 'ProfitMargin' * 100 (e.g., 20.5).\n"
            "   - \"Headcount\": Number of employees from Yahoo Finance 'fullTimeEmployees' or Alpha Vantage 'FullTimeEmployees' (e.g., '164,274' or number).\n"
            "   - \"Salary Average\": Average employee salary; estimate if not available (e.g., '$60,000' or number).\n"
            "   - \"balance_sheet_inventory_cost\": Inventory value from Yahoo Finance 'Inventory' (e.g., '200 million' or number).\n"
            "   Values can be numbers or strings with units (e.g., '$200 million', '300 billion'). If a field is unavailable, set it to \"Not Available\".\n\n"
            "4. **Handle Missing Data and Calculate Benefits**: If any required fields are missing or set to \"Not Available\", use the callback to retry data collection or prompt the user for those values in English. Once all required data is collected, use CalculatorTool to calculate these financial benefits based on the fetched data (do NOT use example values from this prompt):\n"
            "   - \"Margin_Rate_Lift\": {\"low\": value, \"high\": value} (in dollars, derived from Revenue, gross_profit, gross_profit_percentage).\n"
            "   - \"Margin_on_Revenue_Lift\": {\"low\": value, \"high\": value} (in dollars, derived from Revenue, gross_profit, gross_profit_percentage).\n"
            "   - \"Efficiency_Re_Investment\": {\"low\": value, \"high\": value} (in dollars, derived from Headcount and Salary Average, or \"Not Available\" if missing).\n"
            "   - \"Reduction_in_Xfer_Expenses\": {\"low\": value, \"high\": value} (in dollars, derived from balance_sheet_inventory_cost, or \"Not Available\" if missing).\n"
            "   - \"Inventory_Carrying_Costs\": {\"low\": value, \"high\": value} (in dollars, derived from balance_sheet_inventory_cost, or \"Not Available\" if missing).\n"
            "   The callback will handle retries and user prompts if data is insufficient.\n\n"
            "**Available Tools**:\n"
            "- **TickerLookupTool**: Returns a string with the ticker symbol (e.g., \"This is the ticker for 'Tesla Inc.': TSLA\").\n"
            "- **YahooFinanceDataFetcher**: Fetches financial data from Yahoo Finance.\n"
            "- **AlphaVantageDataFetcher**: Fetches financial data from Alpha Vantage to supplement Yahoo Finance.\n"
            "- **InventoryCompanyChecker**: Checks if the company is inventory-based.\n"
            "- **CalculatorTool**: Calculates financial benefits from collected data.\n\n"
            "**Output**: Return only a JSON object with the calculated financial benefits ('Margin_Rate_Lift', 'Margin_on_Revenue_Lift', 'Efficiency_Re_Investment', 'Reduction_in_Xfer_Expenses', 'Inventory_Carrying_Costs') in English, derived from actual data fetched by YahooFinanceDataFetcher and AlphaVantageDataFetcher using CalculatorTool. Do not use example values from this prompt. If data collection fails after retries, the callback will handle the final response."
        )

        return Task(
            description=description,
            expected_output="A JSON object with calculated financial benefits derived from actual fetched data if the company is inventory-based, or a string error message if it’s not.",
            agent=self.agent,
            tools=[
                finance_tools.ticker_lookup_tool,
                finance_tools.yfinance_tool,
                finance_tools.alpha_vantage_tool,
                finance_tools.inventory_check_tool,
                finance_tools.calculator_tool
            ],
            callback=lambda output: collect_missing_data(output, 1)  # Start with attempt 1
        )