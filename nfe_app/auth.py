# -*- coding: utf-8 -*-
"""
Login próprio do sistema (e-mail + senha), pedido de acesso e "esqueci a senha".

Como funciona, em camadas:
  1) PEDIDO DE ACESSO: na tela de login, a pessoa informa nome, e-mail e motivo.
     O pedido fica aguardando; um administrador aprova (tela "Usuários") e o sistema
     manda uma SENHA TEMPORÁRIA para o e-mail dela.
  2) ESQUECI A SENHA: o sistema manda uma senha temporária para o e-mail cadastrado.
     A senha antiga continua valendo até a pessoa entrar com a temporária.
  3) Quem entra com uma senha temporária é OBRIGADO a criar uma senha própria antes
     de usar o sistema. Senhas temporárias vencem (24 h por padrão).
  4) A senha nunca é guardada: só o "hash" dela (veja nfe_app/senhas.py).
  5) Proteção contra adivinhação: 5 senhas erradas seguidas bloqueiam a conta por 15 minutos.
  6) Tempo limite de inatividade e registro de tudo em "registro_acessos".

As consultas ao banco ficam em nfe_app/usuarios_db.py.
"""
import os
import re
import time

import streamlit as st

from nfe_app import tema
from nfe_app import usuarios_db as db
from nfe_app.email_envio import avisar_novo_pedido, email_configurado, enviar_senha_temporaria
from nfe_app.senhas import conferir_senha, problema_na_senha, HASH_FALSO

# Minutos sem nenhuma interação até pedir login de novo (configurável no .env)
MINUTOS_INATIVIDADE = int(os.getenv("LOGIN_MINUTOS_INATIVIDADE", "30"))

# Senhas erradas seguidas até bloquear a conta, e por quantos minutos ela fica bloqueada
MAX_TENTATIVAS = 5
MINUTOS_BLOQUEIO = 15

# (Opcional) domínios de e-mail aceitos nos pedidos de acesso, ex.: "spaguas.sp.gov.br"
DOMINIOS_PERMITIDOS = [
    d.strip().lower().lstrip("@")
    for d in os.getenv("LOGIN_DOMINIOS_PERMITIDOS", "").split(",") if d.strip()
]

# Perfis que existem no sistema (a tabela do banco só aceita estes)
PERFIS = {
    "admin": "Administrador (acesso a todas as telas, inclusive Usuários)",
    "processador": "Processador (processa notas, contratos, aditivos e empenhos + Balanço e Vigência)",
    "consulta": "Consulta (apenas Balanço e Vigência)",
}

# A mesma mensagem para e-mail inexistente e senha errada: assim ninguém usa a
# tela de login para descobrir quais e-mails estão cadastrados.
ERRO_EMAIL_OU_SENHA = "E-mail ou senha incorretos."

# Re-exportado para quem já importava daqui
registrar_acesso = db.registrar_acesso


def _email_valido(email):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "") is not None


# ---------------------------------------------------------------------------
# Conferência do login
# ---------------------------------------------------------------------------
def _tentar_login(email, senha):
    """
    Confere e-mail e senha (a de sempre ou uma temporária ainda no prazo).
    Devolve (usuario, usou_temporaria, None) se deu certo, ou (None, False, mensagem_de_erro).
    """
    usuario = db.buscar_para_login(email)

    if usuario is None:
        conferir_senha(senha, HASH_FALSO)  # mesmo tempo de resposta de um e-mail que existe
        db.registrar_acesso(email, "login_falhou", "e-mail não cadastrado")
        return None, False, ERRO_EMAIL_OU_SENHA

    if usuario["bloqueado"]:
        db.registrar_acesso(email, "login_bloqueado")
        return None, False, (f"Esta conta está bloqueada por excesso de tentativas. Tente de novo em até "
                             f"{MINUTOS_BLOQUEIO} minutos ou use \"Esqueci a senha\" e aguarde o desbloqueio.")

    usou_temporaria = False
    if usuario["senha_hash"] and conferir_senha(senha, usuario["senha_hash"]):
        pass
    elif usuario["senha_temporaria_hash"] and conferir_senha(senha, usuario["senha_temporaria_hash"]):
        usou_temporaria = True
    else:
        db.registrar_acesso(email, "login_falhou", "senha incorreta")
        if db.registrar_senha_errada(usuario["id"], MAX_TENTATIVAS, MINUTOS_BLOQUEIO):
            db.registrar_acesso(email, "conta_bloqueada")
            return None, False, (f"Senha incorreta {MAX_TENTATIVAS} vezes seguidas. Por segurança, a conta "
                                 f"foi bloqueada por {MINUTOS_BLOQUEIO} minutos.")
        return None, False, ERRO_EMAIL_OU_SENHA

    # Só chega aqui quem acertou a senha: aí sim vale explicar a situação da conta
    if not usuario["aprovado"]:
        return None, False, "Seu pedido de acesso ainda está aguardando a aprovação de um administrador."
    if not usuario["ativo"]:
        db.registrar_acesso(email, "usuario_inativo")
        return None, False, "Seu acesso está desativado. Fale com um administrador do sistema."

    db.registrar_login_ok(usuario["id"], apagar_senha_temporaria=not usou_temporaria)
    db.registrar_acesso(email, "login_ok", "com senha temporária" if usou_temporaria else "")
    publico = {chave: usuario[chave] for chave in ("id", "email", "nome", "perfil", "ativo")}
    return publico, usou_temporaria, None


# ---------------------------------------------------------------------------
# Peças visuais
# ---------------------------------------------------------------------------
def _layout_entrada(logo):
    """
    Tela de entrada no estilo da capa da apresentação: um painel azul com o logo e as
    ondas, e o formulário num cartão branco dentro dele. Devolve o espaço do formulário.
    """
    col_capa, col_formulario = st.columns([6.15, 6], gap="large", vertical_alignment="center")
    with col_capa:
        tema.painel_capa(logo)
    with col_formulario:
        tema.marcar_cartao_login()  # faz esta coluna virar o cartão branco dentro do painel azul
        return st.container()


def _ir_para(modo):
    """Troca o que aparece no cartão de login: "entrar", "pedir" ou "esqueci"."""
    st.session_state["_modo_login"] = modo


def _mostrar_aviso():
    """Mostra (uma vez) o recado deixado pela ação anterior: (tipo, texto)."""
    aviso = st.session_state.pop("_aviso_login", None)
    if aviso:
        tipo, texto = aviso
        getattr(st, tipo)(texto)


# ---------------------------------------------------------------------------
# Tela de login (com "Pedir acesso" e "Esqueci a senha")
# ---------------------------------------------------------------------------
def _tela_login(logo=None):
    modo = st.session_state.get("_modo_login", "entrar")
    with _layout_entrada(logo):
        _mostrar_aviso()
        if modo == "pedir":
            _formulario_pedir_acesso()
        elif modo == "esqueci":
            _formulario_esqueci_senha()
        else:
            _formulario_entrar()


def _formulario_entrar():
    tema.rotulo("Acesso restrito")
    st.header("Entrar no sistema")
    st.caption("Use o e-mail e a senha cadastrados.")
    with st.form("form_login", border=False):
        email = st.text_input("E-mail", placeholder="seu.nome@spaguas.sp.gov.br")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary", icon=":material/login:",
                                       use_container_width=True)

    if entrar:
        email = email.strip().lower()
        if not email or not senha:
            st.error("Preencha o e-mail e a senha.")
        else:
            try:
                usuario, usou_temporaria, erro = _tentar_login(email, senha)
            except Exception as erro_banco:
                print(f"[auth] Erro ao conferir o login: {erro_banco}")
                usuario, usou_temporaria, erro = None, False, (
                    "Não foi possível conferir o login (erro no banco de dados). "
                    "Se for a primeira vez, rode 'python scripts/setup_db.py'.")
            if erro:
                st.error(erro)
            else:
                st.session_state["usuario_id"] = usuario["id"]
                st.session_state["_ultima_atividade"] = time.time()
                st.session_state["_trocar_senha_obrigatorio"] = usou_temporaria
                st.rerun()

    col1, col2 = st.columns(2)
    col1.button("Pedir acesso", icon=":material/person_add:", use_container_width=True,
                on_click=_ir_para, args=("pedir",))
    col2.button("Esqueci a senha", icon=":material/lock_reset:", use_container_width=True,
                on_click=_ir_para, args=("esqueci",))


def _formulario_pedir_acesso():
    tema.rotulo("Novo usuário")
    st.header("Pedir acesso")
    st.caption("Um administrador vai analisar o pedido. Se for aprovado, você recebe a senha por e-mail.")
    with st.form("form_pedido", border=False):
        nome = st.text_input("Nome completo")
        email = st.text_input("E-mail institucional", placeholder="seu.nome@spaguas.sp.gov.br")
        motivo = st.text_area("Setor e motivo do acesso", max_chars=300,
                              placeholder="Ex.: Gerência Financeira, para acompanhar a vigência dos contratos.")
        enviar = st.form_submit_button("Enviar pedido", type="primary", use_container_width=True)

    if enviar:
        nome, email, motivo = nome.strip(), email.strip().lower(), motivo.strip()
        dominio = email.rsplit("@", 1)[-1] if "@" in email else ""
        if len(nome) < 3 or not _email_valido(email):
            st.error("Preencha o nome e um e-mail válido.")
        elif DOMINIOS_PERMITIDOS and dominio not in DOMINIOS_PERMITIDOS:
            st.error("Use o seu e-mail institucional (" + ", ".join("@" + d for d in DOMINIOS_PERMITIDOS) + ").")
        else:
            try:
                criado = db.criar_pedido(email, nome, motivo)
                db.registrar_acesso(email, "pedido_acesso" if criado else "pedido_repetido", nome)
            except Exception as erro_banco:
                print(f"[auth] Erro ao gravar pedido de acesso: {erro_banco}")
                st.error("Não foi possível registrar o pedido agora (erro no banco de dados). Tente mais tarde.")
            else:
                if criado:
                    _avisar_administradores(nome, email, motivo)
                # Mesma resposta mesmo se o e-mail já existia (não revela quem está cadastrado)
                st.session_state["_aviso_login"] = (
                    "success", "Pedido enviado! Quando um administrador aprovar, você vai receber "
                               "a senha no e-mail informado.")
                _ir_para("entrar")
                st.rerun()

    st.button("Voltar para o login", icon=":material/arrow_back:", use_container_width=True,
              on_click=_ir_para, args=("entrar",))


def _avisar_administradores(nome, email, motivo):
    """Manda o aviso de novo pedido (EMAIL_AVISO_PEDIDOS no .env). Se falhar, o pedido continua valendo."""
    try:
        avisar_novo_pedido(nome, email, motivo)
    except Exception as erro:
        print(f"[auth] Não foi possível avisar sobre o pedido de {email}: {erro}")
        db.registrar_acesso(email, "falha_envio_email", f"aviso de pedido: {erro}")


def _formulario_esqueci_senha():
    tema.rotulo("Recuperar acesso")
    st.header("Esqueci a senha")
    st.caption("Vamos enviar uma senha temporária para o e-mail cadastrado. "
               "Ao entrar com ela, você cria uma senha nova.")
    if not email_configurado():
        st.warning("O envio de e-mails ainda não está configurado. "
                   "Peça a um administrador para gerar uma nova senha para você.")
    with st.form("form_esqueci", border=False):
        email = st.text_input("E-mail cadastrado")
        enviar = st.form_submit_button("Enviar senha temporária", type="primary", use_container_width=True,
                                       disabled=not email_configurado())

    if enviar:
        email = email.strip().lower()
        if not _email_valido(email):
            st.error("Digite um e-mail válido.")
        else:
            try:
                resultado = db.gerar_senha_temporaria_esqueci(email)
                if resultado:
                    nome, senha_temporaria = resultado
                    enviar_senha_temporaria(email, nome, senha_temporaria,
                                            db.HORAS_SENHA_TEMPORARIA, motivo="esqueci")
                    db.registrar_acesso(email, "senha_temporaria_enviada", "esqueci a senha")
            except Exception as erro:
                # Não mostra o erro na tela (não revela se o e-mail existe); fica no terminal e no registro
                print(f"[auth] Falha no 'esqueci a senha' para {email}: {erro}")
                db.registrar_acesso(email, "falha_envio_email", str(erro))
            st.session_state["_aviso_login"] = (
                "success", "Se este e-mail estiver cadastrado, você vai receber uma senha temporária "
                           "em alguns minutos. Confira também a caixa de spam.")
            _ir_para("entrar")
            st.rerun()

    st.button("Voltar para o login", icon=":material/arrow_back:", use_container_width=True,
              on_click=_ir_para, args=("entrar",))


# ---------------------------------------------------------------------------
# Troca de senha (obrigatória depois de entrar com senha temporária, ou pela página "Minha senha")
# ---------------------------------------------------------------------------
def _formulario_trocar_senha(usuario, obrigatoria):
    with st.form("form_trocar_senha", border=False, clear_on_submit=True):
        atual = "" if obrigatoria else st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password",
                             help="Pelo menos 8 caracteres. Evite datas e nomes fáceis de adivinhar.")
        repetir = st.text_input("Repita a nova senha", type="password")
        salvar = st.form_submit_button("Salvar nova senha", type="primary", use_container_width=True)

    if not salvar:
        return
    if not obrigatoria:
        dados = db.buscar_para_login(usuario["email"])
        if not dados or not dados["senha_hash"] or not conferir_senha(atual, dados["senha_hash"]):
            st.error("A senha atual está incorreta.")
            return
    problema = problema_na_senha(nova)
    if problema:
        st.error(problema)
    elif nova != repetir:
        st.error("As duas senhas não são iguais.")
    else:
        db.trocar_senha(usuario["id"], nova)
        db.registrar_acesso(usuario["email"], "senha_trocada")
        st.session_state["_trocar_senha_obrigatorio"] = False
        st.session_state["_aviso_rapido"] = "Senha alterada com sucesso."
        st.rerun()


def _tela_trocar_senha_obrigatoria(usuario, logo=None):
    with _layout_entrada(logo):
        tema.rotulo("Primeiro acesso")
        st.header("Crie a sua senha")
        st.write("Você entrou com uma senha temporária. Para continuar, crie uma senha só sua.")
        _formulario_trocar_senha(usuario, obrigatoria=True)
        st.button("Sair", icon=":material/logout:", use_container_width=True, on_click=sair)


def pagina_minha_senha():
    """Página "Minha senha" (para todos os perfis)."""
    st.header("🔑 Minha senha")
    _, meio, _ = st.columns([1, 1.3, 1])
    with meio:
        _formulario_trocar_senha(st.session_state["usuario"], obrigatoria=False)


# ---------------------------------------------------------------------------
# Sessão
# ---------------------------------------------------------------------------
def sair(evento="logout", aviso=None):
    """Encerra a sessão: registra a saída e limpa todos os dados da sessão."""
    email = (st.session_state.get("usuario") or {}).get("email")
    if email:
        db.registrar_acesso(email, evento)
    for chave in list(st.session_state.keys()):
        del st.session_state[chave]
    if aviso:
        st.session_state["_aviso_login"] = ("info", aviso)


def exigir_login(logo=None):
    """
    Garante que só entra quem fez login, continua ativo e já criou a própria senha.
    Se não, mostra a tela certa e PARA o app (st.stop) -- nada abaixo roda.
    Devolve o dicionário do usuário: {"id", "email", "nome", "perfil", "ativo", "aprovado"}.
    logo: (opcional) caminho da imagem do logo mostrada nas telas de login.
    """
    # 1) Já entrou nesta sessão?
    if not st.session_state.get("usuario_id"):
        _tela_login(logo)
        st.stop()

    # 2) Tempo limite de inatividade
    agora = time.time()
    ultima = st.session_state.get("_ultima_atividade")
    if ultima and (agora - ultima) > MINUTOS_INATIVIDADE * 60:
        sair("sessao_expirada", aviso="Sua sessão expirou por inatividade. Entre de novo.")
        _tela_login(logo)
        st.stop()
    st.session_state["_ultima_atividade"] = agora

    # 3) Continua autorizado? (consultado a CADA interação: se um admin desativar
    #    alguém, o bloqueio vale na hora, sem esperar a pessoa sair)
    try:
        usuario = db.buscar_por_id(st.session_state["usuario_id"])
    except Exception as erro:
        st.error("Não foi possível verificar a sua autorização (erro no banco de dados). "
                 "Por segurança, o acesso foi bloqueado.")
        print(f"[auth] Erro ao consultar usuários: {erro}")
        st.stop()

    if usuario is None or not usuario["ativo"] or not usuario["aprovado"]:
        sair("usuario_inativo", aviso="Seu acesso foi desativado. Fale com um administrador do sistema.")
        _tela_login(logo)
        st.stop()

    st.session_state["usuario"] = usuario

    # 4) Entrou com senha temporária? Precisa criar a própria senha antes de continuar
    if st.session_state.get("_trocar_senha_obrigatorio"):
        _tela_trocar_senha_obrigatoria(usuario, logo)
        st.stop()

    # Recado rápido deixado pela ação anterior (ex.: "Senha alterada com sucesso.")
    aviso_rapido = st.session_state.pop("_aviso_rapido", None)
    if aviso_rapido:
        st.toast(aviso_rapido, icon="✅")

    return usuario


def mostrar_usuario_na_barra_lateral(usuario):
    """Nome, perfil, aviso de pedidos pendentes (admin) e botão Sair na barra lateral."""
    # Tudo dentro de um container só do usuário (vira um cartão centralizado pelo tema.py,
    # através da classe "st-key-sp_cartao_usuario" que o Streamlit cria a partir do key)
    with st.sidebar.container(key="sp_cartao_usuario"):
        tema.cartao_usuario(usuario.get("nome") or usuario["email"], usuario["email"], usuario["perfil"])
        if usuario["perfil"] == "admin":
            try:
                pendentes = db.contar_pendentes()
            except Exception:
                pendentes = 0
            if pendentes:
                st.warning(f"{pendentes} pedido(s) de acesso aguardando aprovação na tela Usuários.")
        st.button("Sair", icon=":material/logout:", on_click=sair, use_container_width=True, key="sp_botao_sair")
