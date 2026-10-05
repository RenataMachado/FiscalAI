# -*- coding: utf-8 -*-
"""
Modelos SQLAlchemy (ORM) que descrevem as tabelas do banco.

"""
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, Boolean, CheckConstraint, func, true
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

class Usuario(Base):
    """
    Tabela: usuarios -- lista de pessoas AUTORIZADAS a usar o sistema.

    A senha em si NUNCA fica aqui: só o "hash" dela (veja nfe_app/senhas.py).
    Para bloquear alguém, basta ativo = False.
    """
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("perfil IN ('admin', 'processador', 'consulta')", name="ck_usuarios_perfil"),)

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True)  # sempre em minúsculas
    nome = Column(String(255))
    perfil = Column(String(20), nullable=False, server_default="consulta")  # admin | processador | consulta
    ativo = Column(Boolean, nullable=False, server_default=true())
    ultimo_acesso = Column(DateTime(timezone=True))
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    senha_hash = Column(String(255))  # vazio = ainda sem senha (não consegue entrar)
    tentativas_falhas = Column(Integer, nullable=False, server_default="0")  # senhas erradas seguidas
    bloqueado_ate = Column(DateTime(timezone=True))  # preenchido após muitas senhas erradas
    aprovado = Column(Boolean, nullable=False, server_default=true())  # False = pedido de acesso aguardando
    pedido_em = Column(DateTime(timezone=True))
    motivo_pedido = Column(Text)
    senha_temporaria_hash = Column(String(255))  # senha enviada por e-mail (só o hash)
    senha_temporaria_expira = Column(DateTime(timezone=True))
    senha_temporaria_criada_em = Column(DateTime(timezone=True))


class RegistroAcesso(Base):
    """
    Tabela: registro_acessos -- auditoria de entradas no sistema.
    Guarda também as tentativas que deram errado (senha incorreta, conta bloqueada...).
    """
    __tablename__ = "registro_acessos"

    id = Column(Integer, primary_key=True)
    email = Column(String(255))
    evento = Column(String(30))  # login_ok | login_falhou | login_bloqueado | conta_bloqueada | usuario_inativo | logout | sessao_expirada
    # pedido_acesso | acesso_aprovado | pedido_recusado | senha_temporaria_enviada | senha_trocada | ...
    detalhe = Column(Text)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
