"""perfil processador (processa documentos, mas não gerencia usuários)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A regra do banco que limita os perfis passa a aceitar também "processador"
    op.drop_constraint("ck_usuarios_perfil", "usuarios", type_="check")
    op.create_check_constraint(
        "ck_usuarios_perfil", "usuarios", "perfil IN ('admin', 'processador', 'consulta')"
    )


def downgrade() -> None:
    # Antes de voltar, quem era "processador" vira "consulta" (o menor acesso)
    op.execute("UPDATE usuarios SET perfil = 'consulta' WHERE perfil = 'processador'")
    op.drop_constraint("ck_usuarios_perfil", "usuarios", type_="check")
    op.create_check_constraint("ck_usuarios_perfil", "usuarios", "perfil IN ('admin', 'consulta')")
