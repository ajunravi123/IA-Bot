from crewai import Agent, Task, LLM
from groq import Groq  # Keep this import in case you switch back
import os
from config import llm_client
from dotenv import load_dotenv

load_dotenv()

class DataCollectorAgent:
    def __init__(self):
        self.client = llm_client
        
        # Uncomment below if you want to switch back to Groq
        # self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        self.agent = Agent(
            role='Financial Data Collector',
            goal='Collect comprehensive financial data for inventory-based companies',
            backstory='Expert in financial analysis and data collection from multiple sources, specializing in inventory-based companies',
            verbose=True,
            llm=self.client,
            memory=True
        )

    def create_task(self, company_input, finance_tools, websocket):
        async def collect_missing_data(task_output):
            # Expected fields
            required_fields = [
                "company_name", "analyzed_data_date", "balance_sheet_inventory_cost",
                "P&L_inventory_cost", "Revenue", "Headcount Old", "Efficiency Output High",
                "Efficiency Output Low", "Salary Average", "gross_profit",
                "gross_profit_percentage", "market_cap"
            ]
            
            # If task_output is a string (non-inventory message), return it as is
            if isinstance(task_output, str):
                return task_output
            
            # If task_output is a dict, check for missing fields
            if isinstance(task_output, dict):
                missing_items = [field for field in required_fields if field not in task_output or task_output[field] is None]
                if missing_items:
                    await websocket.send_json({
                        "type": "question",
                        "message": f"I couldn't find some data for {company_input}. Could you please provide: {', '.join(missing_items)}?"
                    })
                    response = await websocket.receive_text()
                    # Update task_output with user-provided data (assuming comma-separated values)
                    user_values = response.split(',')
                    for field, value in zip(missing_items, user_values):
                        task_output[field] = value.strip()
                    return task_output
                return task_output
            
            # Fallback for unexpected output
            return {"error": "Unexpected task output format"}

        return Task(
            description=f"""Collect financial data for {company_input} if it's an inventory-based company. 
            Collect data in JSON format with these fields:
            YahooFinanceDataFetcher will return:
            'Inventory',
            'Cost Of Revenue',
            'Total Revenue',
            'Gross Profit',
            'Selling General And Administration',
            'Cost Of Revenue',
            'marketCap',
            'fullTimeEmployees'

            AlphaVantageDataFetcher will be return:

            'Symbol', 
            'AssetType', 
            'Name', 
            'Description', 
            'CIK', 
            'Exchange', 
            'Currency', 
            'Country', 
            'Sector', 
            'Industry', 
            'Address', 
            'OfficialSite', 
            'FiscalYearEnd', 
            'LatestQuarter', 
            'MarketCapitalization', 
            'EBITDA', 
            'PERatio', 
            'PEGRatio', 
            'BookValue', 
            'DividendPerShare', 
            'DividendYield', 
            'EPS', 
            'RevenuePerShareTTM', 
            'ProfitMargin', 
            'OperatingMarginTTM', 
            'ReturnOnAssetsTTM', 
            'ReturnOnEquityTTM', 
            'RevenueTTM', 
            'GrossProfitTTM', 
            'DilutedEPSTTM', 
            'QuarterlyEarningsGrowthYOY', 
            'QuarterlyRevenueGrowthYOY', 
            'AnalystTargetPrice', 
            'AnalystRatingStrongBuy', 
            'AnalystRatingBuy', 
            'AnalystRatingHold', 
            'AnalystRatingSell', 
            'AnalystRatingStrongSell', 
            'TrailingPE', 
            'ForwardPE', 
            'PriceToSalesRatioTTM', 
            'PriceToBookRatio', 
            'EVToRevenue', 
            'EVToEBITDA', 
            'Beta', 
            '52WeekHigh', 
            '52WeekLow'


            Available tools:
            - YahooFinanceDataFetcher: Fetch data from Yahoo Finance
            - AlphaVantageDataFetcher: Fetch data from Alpha Vantage
            - CompanyInfoSearch: Search web for company info
            - FileReadTool: Read local files
            If data is missing, the callback will prompt the user.""",
            expected_output="A JSON object containing the requested financial data if the company is inventory-based, or a string message if it’s not.",
            agent=self.agent,
            tools=[
                finance_tools.yfinance_tool,
                finance_tools.alpha_vantage_tool,
                finance_tools.inventory_check_tool,
                finance_tools.search_company_tool,
                finance_tools.file_read_tool,
            ],
            callback=collect_missing_data
        )