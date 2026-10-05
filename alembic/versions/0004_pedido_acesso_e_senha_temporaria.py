"""pedido de acesso pela tela de login e senha temporaria enviada por e-mail

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FALSE = pedido de acesso aguardando o admin. Quem já está cadastrado fica TRUE.
    op.add_column("usuarios", sa.Column("aprovado", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("usuarios", sa.Column("pedido_em", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("motivo_pedido", sa.Text()))
    # Senha temporária (aprovação ou "esqueci a senha"): só o hash, com prazo de validade
    op.add_column("usuarios", sa.Column("senha_temporaria_hash", sa.String(length=255)))
    op.add_column("usuarios", sa.Column("senha_temporaria_expira", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("senha_temporaria_criada_em", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("usuarios", "senha_temporaria_criada_em")
    op.drop_column("usuarios", "senha_temporaria_expira")
    op.drop_column("usuarios", "senha_temporaria_hash")
    op.drop_column("usuarios", "motivo_pedido")
    op.drop_column("usuarios", "pedido_em")
    op.drop_column("usuarios", "aprovado")
