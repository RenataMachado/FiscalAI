"""criacao das tabelas de login (usuarios, registro_acessos)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("nome", sa.String(length=255)),
        sa.Column("perfil", sa.String(length=20), nullable=False, server_default="consulta"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ultimo_acesso", sa.DateTime(timezone=True)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Só aceita os perfis que o sistema conhece
        sa.CheckConstraint("perfil IN ('admin', 'consulta')", name="ck_usuarios_perfil"),
    )

    op.create_table(
        "registro_acessos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255)),
        sa.Column("evento", sa.String(length=30)),
        sa.Column("detalhe", sa.Text()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_registro_acessos_criado_em", "registro_acessos", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_registro_acessos_criado_em", table_name="registro_acessos")
    op.drop_table("registro_acessos")
    op.drop_table("usuarios")
