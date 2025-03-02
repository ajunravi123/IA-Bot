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
            goal='Collect financial data for inventory-based companies from Yahoo Finance',
            backstory='Expert in financial analysis and data collection from Yahoo Finance, specializing in inventory-based companies',
            verbose=True,
            llm=llm_client,
            memory=True
        )

    def create_task(self, company_input, finance_tools, websocket, max_retries=MAX_RETRIES):
        async def collect_missing_data(task_output, attempt=1):
            required_fields = [
                "company",
                "analized_data_date",
                "balance_sheet_inventory_cost",
                "P&L_inventory_cost",
                "Revenue",
                "Headcount Old",
                "Salary Average",
                "gross_profit",
                "gross_profit_percentage",
                "market_cap",
                "currency"  # Added currency field
            ]
            
            if task_output is None or (isinstance(task_output, str) and not task_output.strip()):
                if attempt < max_retries:
                    await websocket.send_json({
                        "type": "message",
                        "content": f"Attempt {attempt}/{max_retries}: No data collected for '{company_input}'. Retrying..."
                    })
                    await websocket.send_json({"type": "thinking", "status": True})
                    new_task = Task(
                        description=description,
                        expected_output="A JSON object with collected financial data if the company is inventory-based, or a string error message if it’s not.",
                        agent=self.agent,
                        tools=[
                            finance_tools.ticker_lookup_tool,
                            finance_tools.yfinance_tool,
                            finance_tools.alpha_vantage_tool,
                            finance_tools.inventory_check_tool
                        ],
                        callback=lambda output: collect_missing_data(output, attempt + 1)
                    )
                    return await new_task.execute()
                return {"error": f"Failed to collect data for '{company_input}' after {max_retries} attempts - received None or empty output"}
            
            if isinstance(task_output, str):
                if "Error" in task_output or "inventory-based" in task_output:
                    if "No ticker found" in task_output and attempt < max_retries:
                        await websocket.send_json({
                            "type": "message",
                            "content": f"Attempt {attempt}/{max_retries}: Ticker lookup failed for '{company_input}'. Retrying..."
                        })
                        await websocket.send_json({"type": "thinking", "status": True})
                        new_task = Task(
                            description=description,
                            expected_output="A JSON object with collected financial data if the company is inventory-based, or a string error message if it’s not.",
                            agent=self.agent,
                            tools=[
                                finance_tools.ticker_lookup_tool,
                                finance_tools.yfinance_tool,
                                finance_tools.alpha_vantage_tool,
                                finance_tools.inventory_check_tool
                            ],
                            callback=lambda output: collect_missing_data(output, attempt + 1)
                        )
                        return await new_task.execute()
                    return task_output
            
            if isinstance(task_output, dict):
                missing_items = [field for field in required_fields if field not in task_output or task_output[field] is None or task_output[field] == "Not Available"]
                if missing_items:
                    if attempt < max_retries:
                        await websocket.send_json({
                            "type": "message",
                            "content": f"Attempt {attempt}/{max_retries}: Insufficient data for '{company_input}' (missing: {', '.join(missing_items)}). Retrying..."
                        })
                        await websocket.send_json({"type": "thinking", "status": True})
                        new_task = Task(
                            description=description,
                            expected_output="A JSON object with collected financial data if the company is inventory-based, or a string error message if it’s not.",
                            agent=self.agent,
                            tools=[
                                finance_tools.ticker_lookup_tool,
                                finance_tools.yfinance_tool,
                                finance_tools.alpha_vantage_tool,
                                finance_tools.inventory_check_tool
                            ],
                            callback=lambda output: collect_missing_data(output, attempt + 1)
                        )
                        return await new_task.execute()
                    else:
                        await websocket.send_json({
                            "type": "question",
                            "message": f"After {max_retries} attempts, I couldn't find some data for '{company_input}'. Please provide: {', '.join(missing_items)}"
                        })
                        response = await websocket.receive_text()
                        user_values = response.split(',')
                        for field, value in zip(missing_items, user_values):
                            task_output[field] = value.strip()
                
                all_empty = all(
                    task_output[field] == "Not Available" or task_output[field] is None
                    for field in required_fields if field != "company"  # Exclude "company" as it’s the ticker
                )
                if all_empty:
                    return f"No data available to process for '{company_input}' after {max_retries} attempts. Please try again."
                
                summary_parts = [
                    f"{key.replace('_', ' ')}: {task_output.get('currency', '')} {task_output[key]}" if key in ["Revenue", "balance_sheet_inventory_cost", "P&L_inventory_cost", "gross_profit", "market_cap", "Salary Average"]
                    else f"{key.replace('_', ' ')}: {task_output[key]}"
                    for key in required_fields
                    if task_output.get(key) is not None and task_output.get(key) != "Not Available"
                ]
                summary = " ".join(summary_parts) if summary_parts else "Limited data collected."
                
                return {
                    "financial_data": task_output,
                    "summary": summary
                }
            
            return {"error": f"Unexpected task output format for '{company_input}' after {attempt} attempts - received: {task_output}"}

        description = (
            "Process the input '" + company_input + "' to collect financial data for an inventory-based company in English only using multiple tools, with Yahoo Finance as the primary source. Follow these steps:\n\n"
            "1. **Search Company**: Use SearchCompanyTool to search for '" + company_input + "' and identify potential company matches. If '" + company_input + "' is ambiguous (e.g., a partial name or multiple matches), return a list of possible companies (e.g., \"Possible matches for '" + company_input + "': [Company1, Company2]\"). Extract the most likely company name or ticker (if clear) or prompt the user via callback to specify the correct company. If no matches are found, use the callback to retry up to " + str(max_retries) + " times before stopping.\n\n"
            "2. **Find Ticker Symbol**: Use TickerLookupTool to determine the ticker symbol for the identified company or '" + company_input + "'. If '" + company_input + "' is a ticker (1-5 uppercase letters, e.g., 'AAPL'), validate it. If it’s a company name (e.g., 'Tesla Inc.'), find its ticker. The tool will return a string like \"This is the ticker for '" + company_input + "': [ticker]\" (e.g., \"This is the ticker for 'Tesla Inc.': TSLA\"). Extract the ticker symbol (e.g., 'TSLA') from the response. If the ticker cannot be found (e.g., \"Error: No ticker found for '" + company_input + "'\"), use the callback to retry up to " + str(max_retries) + " times before stopping.\n\n"
            "3. **Verify Inventory Status**: Use InventoryCompanyChecker with the ticker from step 2 to confirm the company is inventory-based (has significant inventory on its balance sheet or operates in sectors like consumer goods, industrial, retail, or manufacturing). If not inventory-based, return only the string: \"This application is designed for inventory-based companies only. '" + company_input + "' does not appear to be inventory-based\" and stop processing.\n\n"
            "4. **Read Local Financial Data (Optional)**: Use FileReadTool to check for any locally stored financial data related to the ticker or company from step 2. If local data exists (e.g., JSON or CSV files), extract relevant fields ('company', 'analized_data_date', 'balance_sheet_inventory_cost', 'P&L_inventory_cost', 'Revenue', 'Headcount Old', 'Salary Average', 'gross_profit', 'gross_profit_percentage', 'market_cap', 'currency') and supplement or validate with online data. If no local data is available, proceed to online sources.\n\n"
            "5. **Collect Financial Data**: If the company is inventory-based, gather data in JSON format with these required fields in English using YahooFinanceDataFetcher as the primary source, supplemented by AlphaVantageDataFetcher if needed:\n"
            "   - \"company\": The ticker symbol (e.g., 'TSLA').\n"
            "   - \"analized_data_date\": Date of the latest inventory data (e.g., '2023-12-31').\n"
            "   - \"balance_sheet_inventory_cost\": Inventory value from balance sheet (e.g., '200 million' or number).\n"
            "   - \"P&L_inventory_cost\": Cost of revenue from profit & loss statement (e.g., '$329.5 million' or number).\n"
            "   - \"Revenue\": Total revenue (e.g., '$133.7 billion' or number).\n"
            "   - \"Headcount Old\": Number of employees (e.g., '164,274' or number).\n"
            "   - \"Salary Average\": Average employee salary (e.g., '$60,000' or number).\n"
            "   - \"gross_profit\": Gross profit (e.g., '$98.74 million' or number).\n"
            "   - \"gross_profit_percentage\": Gross profit as percentage of revenue (e.g., 20.5).\n"
            "   - \"market_cap\": Market capitalization (e.g., '$850 billion' or number).\n"
            "   - \"currency\": Currency type of the financial data (e.g., 'USD').\n"
            "   Values can be numbers or strings with units (e.g., '$200 million', '300 billion'). If a field is unavailable, set it to \"Not Available\". Use AlphaVantageDataFetcher to supplement missing data if necessary.\n\n"
            "6. **Handle Missing Data**: If any required fields are missing or set to \"Not Available\", use the callback to retry data collection up to " + str(max_retries) + " times or prompt the user for those values in English after retries fail. If all fields remain \"Not Available\" after retries, the callback will return a message indicating no data is available.\n\n"
            "**Available Tools**:\n"
            "- **SearchCompanyTool**: Searches for company names or tickers and returns possible matches or the most likely company/ticker.\n"
            "- **TickerLookupTool**: Returns a string with the ticker symbol (e.g., \"This is the ticker for 'Tesla Inc.': TSLA\").\n"
            "- **YahooFinanceDataFetcher**: Fetches financial data from Yahoo Finance, including currency type.\n"
            "- **AlphaVantageDataFetcher**: Fetches financial data from Alpha Vantage to supplement Yahoo Finance.\n"
            "- **InventoryCompanyChecker**: Checks if the company is inventory-based.\n"
            "- **FileReadTool**: Reads locally stored financial data (e.g., JSON, CSV) related to the company or ticker.\n\n"
            "**Output**: Return only a JSON object with the collected financial data ('company', 'analized_data_date', 'balance_sheet_inventory_cost', 'P&L_inventory_cost', 'Revenue', 'Headcount Old', 'Salary Average', 'gross_profit', 'gross_profit_percentage', 'market_cap', 'currency') in English, derived from actual data fetched by YahooFinanceDataFetcher, AlphaVantageDataFetcher, and optionally supplemented by FileReadTool and SearchCompanyTool. Do not calculate benefits or use example values—return only the raw collected data with currency information."
        )

        return Task(
            description=description,
            expected_output="A JSON object with collected financial data if the company is inventory-based, or a string error message if it’s not.",
            agent=self.agent,
            tools=[
                finance_tools.ticker_lookup_tool,
                finance_tools.yfinance_tool,
                finance_tools.alpha_vantage_tool,
                finance_tools.file_read_tool,
                finance_tools.search_company_tool,
                finance_tools.inventory_check_tool
            ],
            callback=lambda output: collect_missing_data(output, 1)
        )