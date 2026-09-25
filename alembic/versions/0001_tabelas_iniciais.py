"""criacao das tabelas iniciais (notas_fiscais, resumo_contratos, termos_aditivos, notas_empenho)

Revision ID: 0001
Revises:
Create Date: 2026-09-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notas_fiscais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("Arquivo", sa.Text()),
        sa.Column("numero_nfe", sa.String(length=50)),
        sa.Column("numero_contrato", sa.String(length=100)),
        sa.Column("data_emissao", sa.String(length=20)),
        sa.Column("vencimento", sa.String(length=20)),
        sa.Column("cnpj_emitente", sa.String(length=20)),
        sa.Column("cnpj_pagador", sa.String(length=20)),
        sa.Column("valor_total", sa.Numeric(14, 2)),
        sa.Column("valor_ir", sa.Numeric(14, 2)),
        sa.Column("valor_iss", sa.Numeric(14, 2)),
        sa.Column("valor_liquido", sa.Numeric(14, 2)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "resumo_contratos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_contrato", sa.String(length=100)),
        sa.Column("numero_contrato_spaguas", sa.String(length=100)),
        sa.Column("processo_sei", sa.String(length=100)),
        sa.Column("valor_contrato", sa.Numeric(14, 2)),
        sa.Column("vigencia_contrato", sa.Integer()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "termos_aditivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_contrato", sa.String(length=100)),
        sa.Column("numero_contrato_spaguas", sa.String(length=100)),
        sa.Column("valor_aditivo", sa.Numeric(14, 2)),
        sa.Column("vigencia_aditivo", sa.Integer()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "notas_empenho",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero_ne", sa.String(length=50)),
        sa.Column("processo_sei", sa.String(length=100)),
        sa.Column("cnpj_credor", sa.String(length=20)),
        sa.Column("numero_contrato", sa.String(length=100)),
        sa.Column("natureza_despesa", sa.String(length=100)),
        sa.Column("fonte_recurso", sa.String(length=100)),
        sa.Column("valor_empenhado", sa.Numeric(14, 2)),
        sa.Column("ug", sa.String(length=20)),
        sa.Column("assunto", sa.Text()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notas_empenho")
    op.drop_table("termos_aditivos")
    op.drop_table("resumo_contratos")
    op.drop_table("notas_fiscais")
