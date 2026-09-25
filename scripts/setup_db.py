# -*- coding: utf-8 -*-
"""
Deixa o banco de dados pronto do zero, em uma máquina nova:

    1) Conecta no servidor Postgres (na base de manutenção "postgres",
       que sempre existe) e roda CREATE DATABASE se o banco da
       DATABASE_URL ainda não existir.
    2) Roda `alembic upgrade head` pra criar/atualizar as tabelas
       dentro desse banco.

Uso (sempre que transferir o projeto pra outra máquina):

    python scripts/setup_db.py

Pré-requisitos: o SERVIDOR Postgres já precisa estar rodando e acessível
(local, Docker ou remoto) e o .env já preenchido com DATABASE_URL. Este
script cria o BANCO dentro do servidor — ele não instala o Postgres.
Se você não tem Postgres instalado na máquina nova, veja o
docker-compose.yml na raiz do projeto.
"""
import os
import sys
import subprocess
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não encontrada no .env. Copie .env.example para .env "
        "e preencha antes de rodar este script."
    )


def criar_banco_se_nao_existir() -> None:
    parsed = urlparse(DATABASE_URL)
    nome_banco = parsed.path.lstrip("/")
    if not nome_banco:
        raise RuntimeError("Não consegui identificar o nome do banco dentro da DATABASE_URL.")

    # Conecta na base de manutenção "postgres" (sempre existe em qualquer
    # servidor Postgres), NUNCA no banco alvo — porque se o banco alvo
    # ainda não existe, conectar nele já dá erro.
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname="postgres",
    )
    # CREATE DATABASE não pode rodar dentro de uma transação
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nome_banco,))
            ja_existe = cur.fetchone() is not None

            if ja_existe:
                print(f"[ok] Banco '{nome_banco}' já existe, nada a fazer.")
            else:
                # nome do banco não aceita parâmetro (%s) em DDL, então
                # validamos que só tem caracteres seguros antes de montar a string
                if not nome_banco.replace("_", "").isalnum():
                    raise RuntimeError(
                        f"Nome de banco '{nome_banco}' tem caracteres não usuais; "
                        "crie manualmente por segurança."
                    )
                cur.execute(f'CREATE DATABASE "{nome_banco}"')
                print(f"[ok] Banco '{nome_banco}' criado com sucesso.")
    finally:
        conn.close()


def aplicar_migrations() -> None:
    print("[ok] Aplicando migrations do Alembic (alembic upgrade head)...")
    resultado = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])
    if resultado.returncode != 0:
        sys.exit(resultado.returncode)


if __name__ == "__main__":
    criar_banco_se_nao_existir()
    aplicar_migrations()
    print("[ok] Banco de dados pronto para uso.")
