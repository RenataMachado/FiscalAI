# -*- coding: utf-8 -*-
"""
Deixa o banco de dados pronto do zero, em uma máquina nova:

    1) Verifica se o banco da DATABASE_URL já existe. Se não existir,
       conecta na base de manutenção "postgres" e roda CREATE DATABASE.
    2) Roda `alembic upgrade head` pra criar/atualizar as tabelas.

Uso (sempre que transferir o projeto pra outra máquina):

    python scripts/setup_db.py

Funciona rodando de qualquer pasta (raiz do projeto ou dentro de scripts/).

Pré-requisitos: o SERVIDOR Postgres já precisa estar rodando e acessível
(local, Docker ou remoto) e o .env já preenchido com DATABASE_URL. Este
script cria o BANCO dentro do servidor — ele não instala o Postgres.
Se você não tem Postgres instalado na máquina nova, veja o
docker-compose.yml na raiz do projeto.
"""
import os
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs

from dotenv import load_dotenv
import psycopg2

# Raiz do projeto = pasta acima de scripts/. É lá que ficam o .env e o alembic.ini.
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROJETO / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    sys.exit(
        "[erro] DATABASE_URL não encontrada no .env. Copie .env.example para .env "
        "e preencha antes de rodar este script."
    )


def _dados_conexao(nome_banco):
    """Monta os parâmetros de conexão a partir da DATABASE_URL."""
    parsed = urlparse(DATABASE_URL)
    params = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        # unquote: senhas com caracteres especiais (@, #, %) vêm codificadas na URL
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "dbname": nome_banco,
        "connect_timeout": 10,
    }
    # Repassa opções como ?sslmode=require (bancos na nuvem costumam exigir)
    sslmode = parse_qs(parsed.query).get("sslmode")
    if sslmode:
        params["sslmode"] = sslmode[0]
    return params


def _nome_do_banco():
    nome = unquote(urlparse(DATABASE_URL).path.lstrip("/"))
    if not nome:
        sys.exit("[erro] Não consegui identificar o nome do banco dentro da DATABASE_URL.")
    return nome


def criar_banco_se_nao_existir() -> None:
    nome_banco = _nome_do_banco()

    # 1ª tentativa: conectar direto no banco. Se conectar, ele já existe.
    # (Isso também funciona em serviços na nuvem onde não temos acesso à base "postgres".)
    try:
        psycopg2.connect(**_dados_conexao(nome_banco)).close()
        print(f"[ok] Banco '{nome_banco}' já existe, nada a fazer.")
        return
    except psycopg2.OperationalError as erro:
        if "does not exist" not in str(erro) and "não existe" not in str(erro):
            sys.exit(
                "[erro] Não consegui conectar no servidor Postgres.\n"
                "Verifique se ele está ligado e se usuário/senha/host/porta do .env estão certos.\n"
                f"Detalhe: {erro}"
            )

    # 2ª etapa: o banco não existe -> conecta na base de manutenção "postgres" e cria.
    if not nome_banco.replace("_", "").isalnum():
        sys.exit(
            f"[erro] Nome de banco '{nome_banco}' tem caracteres não usuais; "
            "crie manualmente por segurança."
        )
    try:
        conn = psycopg2.connect(**_dados_conexao("postgres"))
    except psycopg2.OperationalError as erro:
        sys.exit(f"[erro] Não consegui conectar na base 'postgres' para criar o banco.\nDetalhe: {erro}")

    # CREATE DATABASE não pode rodar dentro de uma transação
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{nome_banco}"')
        print(f"[ok] Banco '{nome_banco}' criado com sucesso.")
    except psycopg2.errors.InsufficientPrivilege:
        sys.exit(f"[erro] O usuário do .env não tem permissão para criar bancos. Crie '{nome_banco}' manualmente.")
    finally:
        conn.close()


def aplicar_migrations() -> None:
    print("[ok] Aplicando migrations do Alembic (alembic upgrade head)...")
    # cwd=RAIZ_PROJETO garante que o alembic.ini seja encontrado
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ_PROJETO,
    )
    if resultado.returncode != 0:
        print(
            "\n[dica] Se o erro for 'relation ... already exists', as tabelas foram criadas "
            "antes do Alembic (pelo pandas). Nesse caso rode UMA vez:\n"
            "    alembic stamp head\n"
            "para marcar o banco como atualizado, e depois rode este script de novo."
        )
        sys.exit(resultado.returncode)


if __name__ == "__main__":
    criar_banco_se_nao_existir()
    aplicar_migrations()
    print("[ok] Banco de dados pronto para uso.")
