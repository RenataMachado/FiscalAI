""""
Configuração central: conexão com o banco de dados PostgreSQL e cliente da API da Anthropic (Claude).
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
import anthropic

# Carrega as variáveis de ambiente do .env
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("A variável DATABASE_URL não foi encontrada. Verifique o arquivo .env!")

engine = create_engine(DB_URL)

ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

# Quantas vezes o próprio SDK da Anthropic tenta de novo quando a API responde "ocupado"
# (429, 500, 529...) ou quando a conexão cai. Ele espera um pouco mais a cada tentativa
# e respeita o tempo de espera que a própria Anthropic informa na resposta.
ANTHROPIC_TENTATIVAS = int(os.getenv("ANTHROPIC_TENTATIVAS", "4"))

# Tempo máximo (em segundos) esperando UMA resposta antes de desistir e tentar de novo.
ANTHROPIC_TIMEOUT = 180

# Inicializa como None por padrão. Assim, a importação no outro arquivo nunca quebra,
# e a mensagem de erro da IA será mostrada corretamente na tela do Streamlit.
client = None

if ANTHROPIC_API_KEY:
    client = anthropic.Anthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=ANTHROPIC_TENTATIVAS,
        timeout=ANTHROPIC_TIMEOUT,
    )
