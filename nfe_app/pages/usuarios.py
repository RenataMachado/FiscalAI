# -*- coding: utf-8 -*-
"""
Tela "Usuários" (só para administradores):
  - cadastrar novos usuários diretamente (sem a pessoa precisar pedir acesso);
  - aprovar ou recusar os pedidos de acesso feitos na tela de login;
  - alterar perfil, desativar/reativar e gerar nova senha para quem já tem acesso.

Ao aprovar (ou gerar nova senha), o sistema cria uma senha temporária e manda por e-mail.
Se o e-mail não estiver configurado ou falhar, a senha aparece aqui na tela UMA vez,
para o administrador repassar por outro meio.
"""
import re

import pandas as pd
import streamlit as st

from nfe_app import usuarios_db as db
from nfe_app.auth import PERFIS
from nfe_app.email_envio import email_configurado, enviar_senha_temporaria

# Do menor para o maior acesso ("consulta" primeiro: na dúvida, o menor acesso)
OPCOES_PERFIL = ["consulta", "processador", "admin"]


def _guardar_aviso(tipo, texto):
    st.session_state["_aviso_usuarios"] = (tipo, texto)


def _mostrar_aviso():
    aviso = st.session_state.pop("_aviso_usuarios", None)
    if aviso:
        tipo, texto = aviso
        getattr(st, tipo)(texto)


def _entregar_senha(email, nome, senha, motivo, acao_ok):
    """Tenta mandar a senha temporária por e-mail; se não der, mostra ao admin para repassar."""
    horas = db.HORAS_SENHA_TEMPORARIA
    try:
        enviar_senha_temporaria(email, nome, senha, horas, motivo=motivo)
        db.registrar_acesso(email, "senha_temporaria_enviada", motivo)
        _guardar_aviso("success", f"{acao_ok} A senha temporária foi enviada para {email}.")
    except Exception as erro:
        print(f"[usuarios] Falha ao enviar e-mail para {email}: {erro}")
        db.registrar_acesso(email, "falha_envio_email", str(erro))
        _guardar_aviso(
            "warning",
            f"{acao_ok} Mas o e-mail NÃO foi enviado ({erro}).\n\n"
            f"Repasse esta senha temporária para {email} por outro meio: **{senha}**\n\n"
            f"Ela vale por {horas} horas e só aparece agora. No primeiro acesso, a pessoa cria uma senha própria."
        )


# Formato básico de e-mail: algo@algo.algo (sem espaços)
FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _secao_adicionar(eu):
    st.subheader("Adicionar usuário")
    st.caption("Cadastre alguém diretamente, sem a pessoa precisar pedir acesso. O sistema cria uma "
               "senha temporária e envia por e-mail (ou mostra aqui, se o e-mail não estiver configurado). "
               "No primeiro acesso, a pessoa cria uma senha própria.")

    # clear_on_submit: limpa os campos depois de cadastrar
    with st.form("form_adicionar_usuario", clear_on_submit=True, border=True):
        col_nome, col_email = st.columns(2)
        nome = col_nome.text_input("Nome completo", max_chars=120)
        email = col_email.text_input("E-mail institucional", max_chars=200,
                                     placeholder="nome@spaguas.sp.gov.br")
        perfil = st.selectbox("Perfil", OPCOES_PERFIL, format_func=PERFIS.get)
        enviado = st.form_submit_button("Cadastrar usuário", type="primary", icon=":material/person_add:")

    if not enviado:
        return

    nome = nome.strip()
    email = email.strip().lower()
    if not nome or not email:
        st.error("Preencha o nome e o e-mail.")
        return
    if not FORMATO_EMAIL.match(email):
        st.error(f"'{email}' não parece um e-mail válido.")
        return

    novo_id = db.criar_usuario_pelo_admin(email, nome, perfil)
    if novo_id is None:
        if db.situacao_do_email(email) == "pendente":
            st.warning(f"{email} já fez um pedido de acesso. Aprove o pedido na seção abaixo.")
        else:
            st.warning(f"{email} já está cadastrado. Para mudar o perfil ou gerar nova senha, "
                       f"use \"Alterar um usuário\", mais abaixo.")
        return

    db.registrar_acesso(email, "usuario_criado_pelo_admin", f"perfil {perfil}, por {eu['email']}")
    senha = db.gerar_senha_temporaria_pelo_admin(novo_id)
    _entregar_senha(email, nome, senha, "cadastro", f"Usuário {email} cadastrado como '{perfil}'.")
    st.rerun()


def _secao_pedidos(eu, pendentes):
    st.subheader(f"Pedidos de acesso ({len(pendentes)})")
    if not pendentes:
        st.caption("Nenhum pedido aguardando aprovação.")
        return

    for pedido in pendentes:
        pid = pedido["id"]
        with st.container(border=True):
            st.markdown(f"**{pedido['nome'] or '(sem nome)'}** — {pedido['email']}")
            quando = pedido["pedido_em"].strftime("%d/%m/%Y %H:%M") if pedido["pedido_em"] else "-"
            st.caption(f"Pedido em {quando}. Motivo: {pedido['motivo_pedido'] or '(não informado)'}")

            col_perfil, col_aprovar, col_recusar = st.columns([2, 1, 1], vertical_alignment="bottom")
            perfil = col_perfil.selectbox("Perfil", OPCOES_PERFIL, format_func=PERFIS.get, key=f"perfil_pedido_{pid}")

            if col_aprovar.button("Aprovar", type="primary", icon=":material/check:",
                                  use_container_width=True, key=f"aprovar_{pid}"):
                aprovado = db.aprovar_pedido(pid, perfil)
                if aprovado:
                    db.registrar_acesso(aprovado["email"], "acesso_aprovado", f"perfil {perfil}, por {eu['email']}")
                    senha = db.gerar_senha_temporaria_pelo_admin(pid)
                    _entregar_senha(aprovado["email"], aprovado["nome"], senha, "aprovacao",
                                    f"Acesso de {aprovado['email']} aprovado como '{perfil}'.")
                st.rerun()

            if col_recusar.button("Recusar", icon=":material/close:", use_container_width=True,
                                  key=f"recusar_{pid}"):
                email = db.recusar_pedido(pid)
                if email:
                    db.registrar_acesso(email, "pedido_recusado", f"por {eu['email']}")
                    _guardar_aviso("info", f"Pedido de {email} recusado e removido.")
                st.rerun()


def _texto_situacao_senha(u):
    if u["bloqueado"]:
        return "bloqueada (muitas tentativas)"
    if u["tem_temporaria"]:
        return "temporária enviada"
    return "ok" if u["tem_senha"] else "sem senha"


def _secao_usuarios(eu, usuarios):
    st.subheader(f"Usuários com acesso ({len(usuarios)})")
    if not usuarios:
        st.caption("Ninguém cadastrado ainda.")
        return

    tabela = pd.DataFrame([{
        "Nome": u["nome"] or "",
        "E-mail": u["email"],
        "Perfil": u["perfil"],
        "Ativo": "sim" if u["ativo"] else "não",
        "Senha": _texto_situacao_senha(u),
        "Último acesso": u["ultimo_acesso"].strftime("%d/%m/%Y %H:%M") if u["ultimo_acesso"] else "-",
    } for u in usuarios])
    st.dataframe(tabela, hide_index=True, use_container_width=True)

    # A própria conta fica de fora (evita o admin se desativar ou se tirar o perfil sem querer)
    outros = {u["id"]: u for u in usuarios if u["id"] != eu["id"]}
    st.markdown("**Alterar um usuário**")
    if not outros:
        st.caption("Não há outros usuários para alterar. A sua própria conta não pode ser alterada aqui.")
        return

    uid = st.selectbox("Usuário", list(outros),
                       format_func=lambda i: f"{outros[i]['nome'] or outros[i]['email']} ({outros[i]['email']})")
    alvo = outros[uid]

    col_perfil, col_salvar = st.columns([2, 1], vertical_alignment="bottom")
    novo_perfil = col_perfil.selectbox("Perfil", OPCOES_PERFIL, index=OPCOES_PERFIL.index(alvo["perfil"]),
                                       format_func=PERFIS.get, key=f"perfil_usuario_{uid}")
    if col_salvar.button("Salvar perfil", use_container_width=True, disabled=novo_perfil == alvo["perfil"]):
        db.alterar_perfil(uid, novo_perfil)
        db.registrar_acesso(alvo["email"], "perfil_alterado", f"{alvo['perfil']} -> {novo_perfil}, por {eu['email']}")
        _guardar_aviso("success", f"Perfil de {alvo['email']} alterado para '{novo_perfil}'.")
        st.rerun()

    col_ativo, col_senha = st.columns(2)
    if alvo["ativo"]:
        if col_ativo.button("Desativar acesso", icon=":material/block:", use_container_width=True):
            db.alterar_ativo(uid, False)
            db.registrar_acesso(alvo["email"], "usuario_desativado", f"por {eu['email']}")
            _guardar_aviso("info", f"Acesso de {alvo['email']} desativado (vale na próxima interação dele).")
            st.rerun()
    else:
        if col_ativo.button("Reativar acesso", icon=":material/check_circle:", use_container_width=True):
            db.alterar_ativo(uid, True)
            db.registrar_acesso(alvo["email"], "usuario_reativado", f"por {eu['email']}")
            _guardar_aviso("success", f"Acesso de {alvo['email']} reativado.")
            st.rerun()

    if col_senha.button("Gerar nova senha", icon=":material/lock_reset:", use_container_width=True,
                        disabled=not alvo["ativo"],
                        help="Cria uma senha temporária, desbloqueia a conta e envia por e-mail."):
        senha = db.gerar_senha_temporaria_pelo_admin(uid)
        _entregar_senha(alvo["email"], alvo["nome"], senha, "admin", f"Nova senha gerada para {alvo['email']}.")
        st.rerun()


def gerenciar_usuarios():
    st.header("👥 Usuários")
    eu = st.session_state["usuario"]

    if not email_configurado():
        st.info("O envio de e-mails ainda não está configurado (linhas SMTP_ no .env). Enquanto isso, "
                "as senhas temporárias aparecem aqui na tela para você repassar a cada pessoa.")
    _mostrar_aviso()

    # Só a leitura fica dentro do try (o st.rerun dos botões não pode ser "engolido" por ele)
    try:
        pendentes = db.listar_pendentes()
        usuarios = db.listar_usuarios()
    except Exception as erro:
        print(f"[usuarios] Erro: {erro}")
        st.error("Não foi possível carregar os usuários (erro no banco de dados). "
                 "Se acabou de atualizar o sistema, rode 'python scripts/setup_db.py'.")
        return

    _secao_adicionar(eu)
    st.divider()
    _secao_pedidos(eu, pendentes)
    st.divider()
    _secao_usuarios(eu, usuarios)
