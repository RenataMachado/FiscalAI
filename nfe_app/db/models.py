# -*- coding: utf-8 -*-
"""
Modelos SQLAlchemy (ORM) que descrevem as tabelas do banco.

Estas classes NAO mudam a forma como o app grava dados (ele continua
usando pandas `to_sql` / `read_sql` normalmente, igual sempre foi).
Elas servem só para o Alembic saber "como a tabela deveria ser" e
gerar/aplicar as migrations de criação/alteração de tabelas.

Os nomes de tabela e de coluna abaixo foram tirados exatamente do que
o código original gravava com `to_sql(...)`, então os dados antigos
continuam compatíveis.
"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class NotaFiscal(Base):
    """Tabela: notas_fiscais (gravada em ui_helpers.armazena_info)."""
    __tablename__ = "notas_fiscais"

    id = Column(Integer, primary_key=True)
    Arquivo = Column(Text)
    numero_nfe = Column(String(50))
    numero_contrato = Column(String(100))
    data_emissao = Column(String(20))   # formato 'AAAA-MM-DD' (string, como o app já grava)
    vencimento = Column(String(20))     # formato 'AAAA-MM-DD'
    cnpj_emitente = Column(String(20))
    cnpj_pagador = Column(String(20))
    valor_total = Column(Numeric(14, 2))
    valor_ir = Column(Numeric(14, 2))
    valor_iss = Column(Numeric(14, 2))
    valor_liquido = Column(Numeric(14, 2))
    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class ResumoContrato(Base):
    """Tabela: resumo_contratos (gravada em pages.contratos.gerenciar_contratos)."""
    __tablename__ = "resumo_contratos"

    id = Column(Integer, primary_key=True)
    numero_contrato = Column(String(100))
    numero_contrato_spaguas = Column(String(100))
    processo_sei = Column(String(100))
    valor_contrato = Column(Numeric(14, 2))
    vigencia_contrato = Column(Integer)  # meses
    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class TermoAditivo(Base):
    """Tabela: termos_aditivos (gravada em pages.aditivos.gerenciar_aditivos)."""
    __tablename__ = "termos_aditivos"

    id = Column(Integer, primary_key=True)
    numero_contrato = Column(String(100))
    numero_contrato_spaguas = Column(String(100))
    valor_aditivo = Column(Numeric(14, 2))
    vigencia_aditivo = Column(Integer)  # meses extras
    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class NotaEmpenho(Base):
    """Tabela: notas_empenho (gravada em pages.empenhos.gerenciar_empenhos)."""
    __tablename__ = "notas_empenho"

    id = Column(Integer, primary_key=True)
    numero_ne = Column(String(50))
    processo_sei = Column(String(100))
    cnpj_credor = Column(String(20))
    numero_contrato = Column(String(100))
    natureza_despesa = Column(String(100))
    fonte_recurso = Column(String(100))
    valor_empenhado = Column(Numeric(14, 2))
    ug = Column(String(20))
    assunto = Column(Text)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
