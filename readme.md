# Impact Financial Chatbot Application

**Author**: Ajun Ravi  
**Email**: ajunravi123@gmail.com  

A modern, real-time financial analysis chatbot built with FastAPI, CrewAI, and a WebSocket-based frontend. This application allows users to input a company name or ticker symbol and receive detailed financial metrics and a summary, specifically tailored for inventory-based companies. It features a sleek dark-themed UI with animations and leverages multiple data sources (Yahoo Finance, Alpha Vantage) and a local LLM for processing.

---

## 🚀 Features
- **Real-Time Interaction**: WebSocket-based chat interface for instant responses.
- **Financial Analysis**: Collects metrics like revenue, gross profit, market cap, and more for inventory-based companies.
- **Agentic AI**: Uses CrewAI with multiple agents (Data Collector, Data Formatter, Summary Generator) powered by a local LLM.
- **Dynamic UI**: Dark theme with fade-in animations, a custom CSS thinking animation, and responsive design.
- **Data Sources**: Integrates Yahoo Finance and Alpha Vantage APIs for financial data.
- **User Input**: Prompts users for missing data via the chat interface.

---

## 📌 Prerequisites
- **Python 3.9+**
- A local LLM server (e.g., Ollama) running at `http://localhost:11434` (Optional: Groq API key as an alternative).
- **API keys required:**
  - Alpha Vantage (`ALPHA_VANTAGE_API_KEY`)
  - Serper (`SERPER_API_KEY`) for web search (optional)

---

## 🛠 Installation
### 1️⃣ Clone the Repository:
```sh
git clone <repository-url>
cd financial-chatbot
```

### 2️⃣ Install Dependencies:
Create a virtual environment and install the required packages:
```sh
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3️⃣ Set Up Environment Variables:
Create a `.env` file in the project root and add:
```ini
MODEL_NAME=<your-llm-model>  # e.g., "llama3" for Ollama
ALPHA_VANTAGE_API_KEY=<your-alpha-vantage-key>
SERPER_API_KEY=<your-serper-key>
GROQ_API_KEY=<your-groq-key>  # Optional, if using Groq
```

### 4️⃣ Run the Local LLM Server (if using Ollama):
```sh
ollama run <your-model-name>
```

---

## 🚀 Usage
### 1️⃣ Start the Application:
```sh
uvicorn main:app --reload
```

### 2️⃣ Access the Chatbot:
Open a browser and navigate to `http://localhost:8000`. Enter a company name or ticker (e.g., `AAPL`) in the input field and press **Send** or **Enter**.

### 3️⃣ Interact with the Bot:
- The bot will display a **thinking animation** during processing.
- If the company **isn’t inventory-based**, you’ll see a message.
- If **data is missing**, you’ll be prompted to provide it (comma-separated values).
- Final output includes a **table of metrics** and a **summary**.

---

## 📂 File Structure
```
financial-chatbot/
├── agents/                  # Agent definitions
│   ├── __init__.py
│   ├── data_collector.py
│   ├── data_formatter.py
│   └── summary_generator.py
├── tools/                   # Custom tools for data collection
│   ├── __init__.py
│   └── finance_tools.py
├── static/                  # Static assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── app.js
├── templates/               # HTML templates
│   └── index.html
├── config.py                # Centralized LLM configuration
├── main.py                  # FastAPI application
├── .env                     # Environment variables (not tracked)
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## 🔧 Project Details
- **Backend**: FastAPI with WebSocket support, CrewAI for agentic workflows.
- **Frontend**: Bootstrap 5, jQuery, custom CSS animations.
- **Agents**:
  - `DataCollectorAgent`: Fetches financial data, checks inventory status.
  - `DataFormatterAgent`: Formats data into JSON.
  - `SummaryGeneratorAgent`: Generates a natural language summary.
- **Tools**: Yahoo Finance, Alpha Vantage API, Serper (web search), FileReadTool.
- **LLM**: Configurable via `config.py` (default: local LLM at `http://localhost:11434`).

---

## 📜 Requirements
Dependencies listed in `requirements.txt`:
```sh
fastapi
uvicorn
crewai
crewai_tools
yfinance
alpha_vantage
python-dotenv
jinja2
websockets
requests
groq  # Optional, if using Groq LLM
```

---

## 🛠 Troubleshooting
- **LLM Not Responding**: Ensure the local LLM server is running (`http://localhost:11434`) and `MODEL_NAME` is set in `.env`.
- **API Errors**: Verify API keys in `.env` and check rate limits (Alpha Vantage: 5 calls/min free tier).
- **WebSocket Issues**: Open browser dev tools (**Network > WS**) to inspect messages.

---

## 🌟 Future Improvements
✅ Add caching for API calls to improve performance.  
✅ Support more data sources (e.g., SEC filings).  
✅ Enhance user input parsing (e.g., JSON instead of comma-separated values).  
✅ Add a **light theme** option.

---


## 🤝 Contributing
Pull requests and issues are welcome! Please ensure tests pass and follow the coding style.

**Built with ❤️ by Ajun Ravi** 🚀