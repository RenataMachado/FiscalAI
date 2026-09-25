"""
Configuração central: conexão com o banco de dados PostgreSQL e cliente da API Gemini (IA).
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from google import genai

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("A variável DATABASE_URL não foi encontrada. Verifique o arquivo .env!")

engine = create_engine(DB_URL)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
