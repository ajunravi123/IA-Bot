# config.py
from crewai import LLM
from dotenv import load_dotenv
import os

load_dotenv()

# Define the LLM here. In my local I'm using ollama deepseek model
llm_client = LLM(
    model=os.getenv("MODEL_NAME"),
    base_url="http://localhost:11434", # needed it only if using ollama
    api_key="ollama" #while running local model, a dummy api key is reuired.
)

