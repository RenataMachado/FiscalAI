"""login proprio com senha (sai o login Microsoft)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Hash da senha (nunca a senha em si). Vazio = a pessoa ainda não tem senha e não consegue entrar.
    op.add_column("usuarios", sa.Column("senha_hash", sa.String(length=255)))
    # Proteção contra adivinhação de senha
    op.add_column("usuarios", sa.Column("tentativas_falhas", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("usuarios", sa.Column("bloqueado_ate", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("usuarios", "bloqueado_ate")
    op.drop_column("usuarios", "tentativas_falhas")
    op.drop_column("usuarios", "senha_hash")
