# -*- coding: utf-8 -*-
import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Garante que a pasta do projeto (raiz, onde fica a pasta nfe_app/) esteja
# no sys.path, para o "from nfe_app.db.models import Base" funcionar
# independente de onde o comando `alembic` for chamado.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nfe_app.db.models import Base  # noqa: E402

# Carrega o .env do projeto (mesma variável DATABASE_URL usada pelo app)
load_dotenv()

# Config do Alembic (lê o alembic.ini)
config = context.config

# Injeta a URL do banco vinda do .env — nunca fica hardcoded no alembic.ini
db_url = os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError(
        "A variável DATABASE_URL não foi encontrada. Verifique o arquivo .env "
        "na raiz do projeto antes de rodar o Alembic."
    )
config.set_main_option("sqlalchemy.url", db_url)

# Configuração de logging do alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata usada pelo --autogenerate para comparar models vs. banco real
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera o SQL das migrations sem se conectar de fato ao banco
    (útil para revisar/gerar um script .sql antes de aplicar)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Conecta no banco (via DATABASE_URL) e aplica as migrations de fato."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
