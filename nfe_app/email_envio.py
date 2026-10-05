# -*- coding: utf-8 -*-
"""
Envio de e-mails do sistema (senha temporária) por SMTP, com a biblioteca padrão do Python.

Configuração no .env (veja .env.example):
    SMTP_HOST, SMTP_PORTA, SMTP_SEGURANCA, SMTP_USUARIO, SMTP_SENHA, SMTP_REMETENTE
    APP_URL (opcional: endereço do sistema, para aparecer no e-mail)
    EMAIL_AVISO_PEDIDOS (opcional: quem recebe o aviso de cada novo pedido de acesso)

Para testar sem abrir o sistema:
    python scripts/testar_email.py seu.email@exemplo.com
"""
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from dotenv import load_dotenv

load_dotenv()

NOME_SISTEMA = "Sistema de Gestão de Notas Fiscais"


def _config(nome, padrao=""):
    return (os.getenv(nome) or padrao).strip()


def email_configurado():
    """True se o .env tem pelo menos o servidor de e-mail (SMTP_HOST)."""
    return bool(_config("SMTP_HOST"))


def enviar_email(destino, assunto, texto):
    """
    Envia um e-mail de texto simples.
    Em caso de problema, lança RuntimeError com uma mensagem em português dizendo o que conferir.
    """
    host = _config("SMTP_HOST")
    porta = int(_config("SMTP_PORTA", "587"))
    seguranca = _config("SMTP_SEGURANCA", "starttls").lower()  # starttls | ssl | nenhuma
    usuario = _config("SMTP_USUARIO")
    senha = _config("SMTP_SENHA")
    remetente = _config("SMTP_REMETENTE") or usuario

    if not host:
        raise RuntimeError("O envio de e-mail não está configurado (SMTP_HOST vazio no .env).")
    if not remetente:
        raise RuntimeError("Defina SMTP_REMETENTE (ou SMTP_USUARIO) no .env.")

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = formataddr((NOME_SISTEMA, remetente))
    mensagem["To"] = destino
    # quoted-printable: acentos chegam certos em qualquer servidor de e-mail
    mensagem.set_content(texto, cte="quoted-printable")

    contexto = ssl.create_default_context()
    try:
        if seguranca == "ssl":
            servidor = smtplib.SMTP_SSL(host, porta, timeout=20, context=contexto)
        else:
            servidor = smtplib.SMTP(host, porta, timeout=20)
        with servidor:
            if seguranca == "starttls":
                servidor.starttls(context=contexto)
            if usuario:
                servidor.login(usuario, senha)
            servidor.send_message(mensagem)
    except smtplib.SMTPAuthenticationError as erro:
        raise RuntimeError(
            "O servidor de e-mail recusou o usuário/senha do SMTP. Confira SMTP_USUARIO e SMTP_SENHA. "
            "Se for e-mail da Microsoft (Outlook), a TI precisa liberar o envio por SMTP para essa conta. "
            f"Detalhe: {erro}"
        ) from erro
    except smtplib.SMTPException as erro:
        raise RuntimeError(f"O servidor de e-mail recusou o envio. Detalhe: {erro}") from erro
    except OSError as erro:  # sem rede, endereço errado, porta bloqueada, tempo esgotado
        raise RuntimeError(
            f"Não foi possível conectar ao servidor de e-mail {host}:{porta}. "
            f"Confira SMTP_HOST, SMTP_PORTA e SMTP_SEGURANCA. Detalhe: {erro}"
        ) from erro


def enviar_senha_temporaria(destino, nome, senha, horas_validade, motivo):
    """
    motivo: "cadastro"   -> o administrador criou a conta da pessoa
            "aprovacao"  -> pedido de acesso aprovado
            "admin"      -> o administrador gerou uma senha nova
            "esqueci"    -> a própria pessoa pediu em "Esqueci a senha"
    """
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    url = _config("APP_URL")
    linha_link = f"\nAcesse o sistema em: {url}\n" if url else ""

    if motivo == "cadastro":
        assunto = f"Seu acesso ao {NOME_SISTEMA}"
        abertura = f"Um administrador criou o seu acesso ao {NOME_SISTEMA}. Para entrar, use o seu e-mail e a senha abaixo."
        rodape = "Se você não esperava esta mensagem, avise o administrador do sistema."
    elif motivo == "aprovacao":
        assunto = f"Seu acesso ao {NOME_SISTEMA} foi aprovado"
        abertura = f"Seu pedido de acesso ao {NOME_SISTEMA} foi aprovado."
        rodape = "Se você não pediu acesso, ignore este e-mail."
    elif motivo == "esqueci":
        assunto = f"Senha temporária do {NOME_SISTEMA}"
        abertura = f"Recebemos um pedido para redefinir a sua senha do {NOME_SISTEMA}."
        rodape = "Se não foi você, ignore este e-mail: a sua senha atual continua valendo."
    else:
        assunto = f"Nova senha temporária do {NOME_SISTEMA}"
        abertura = f"Um administrador gerou uma nova senha temporária para você no {NOME_SISTEMA}."
        rodape = "Se você não esperava esta mensagem, avise o administrador do sistema."

    texto = (
        f"{saudacao}\n\n"
        f"{abertura}\n\n"
        f"Sua senha temporária é: {senha}\n\n"
        f"Ela vale por {horas_validade} horas. Ao entrar com ela, o sistema vai pedir "
        f"que você crie uma senha só sua.\n"
        f"{linha_link}\n"
        f"{rodape}\n"
    )
    enviar_email(destino, assunto, texto)


def avisar_novo_pedido(nome, email, motivo):
    """
    Avisa por e-mail que chegou um pedido de acesso, para os endereços de
    EMAIL_AVISO_PEDIDOS no .env (pode ter mais de um, separados por vírgula).
    Devolve False (sem fazer nada) se não houver destinatário ou e-mail configurado.
    """
    destinos = [d.strip() for d in _config("EMAIL_AVISO_PEDIDOS").split(",") if d.strip()]
    if not destinos or not email_configurado():
        return False
    url = _config("APP_URL")
    texto = (
        f"Chegou um novo pedido de acesso ao {NOME_SISTEMA}.\n\n"
        f"Nome: {nome}\n"
        f"E-mail: {email}\n"
        f"Setor e motivo: {motivo or '(não informado)'}\n\n"
        f"Para aprovar ou recusar, entre no sistema e abra a tela Usuários."
        + (f"\n{url}\n" if url else "\n")
    )
    enviar_email(", ".join(destinos), f"Novo pedido de acesso: {nome}", texto)
    return True
