# -*- coding: utf-8 -*-
"""
Diagnóstico do envio de e-mail, passo a passo. NÃO mostra a senha.

Uso (na raiz do projeto):
    python scripts/diagnostico_email.py seu.email@destino.com
"""
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent.parent
v = {k: (val or "").strip() for k, val in dotenv_values(RAIZ / ".env").items()}
host, porta = v.get("SMTP_HOST", ""), int(v.get("SMTP_PORTA") or 587)
seguranca = (v.get("SMTP_SEGURANCA") or "starttls").lower()
usuario, senha = v.get("SMTP_USUARIO", ""), v.get("SMTP_SENHA", "")
remetente = v.get("SMTP_REMETENTE") or usuario
destino = sys.argv[1] if len(sys.argv) > 1 else usuario

print("=== Configuração lida do .env ===")
print(f"  servidor ........ {host}:{porta} ({seguranca})")
print(f"  usuário ......... ...{usuario[usuario.find('@'):] if '@' in usuario else '(sem @)'}")
print(f"  senha ........... {len(senha)} caracteres"
      + ("  <-- senha de app do Gmail tem 16 letras" if "gmail" in host and len(senha) != 16 else ""))
print(f"  remetente ....... ...{remetente[remetente.find('@'):] if '@' in remetente else '(sem @)'}")
if "gmail" in host and not usuario.lower().endswith("@gmail.com"):
    print("  ATENÇÃO: o servidor é o Gmail, mas o usuário não é um endereço @gmail.com.")
print()


def passo(nome, funcao):
    print(f"[ .. ] {nome}", end="", flush=True)
    try:
        resultado = funcao()
        print(f"\r[ ok ] {nome}")
        return resultado
    except Exception as erro:
        print(f"\r[FALHOU] {nome}")
        print(f"         tipo: {type(erro).__name__}")
        print(f"         detalhe: {erro}")
        sys.exit(1)


contexto = ssl.create_default_context()
if seguranca == "ssl":
    s = passo("1. Conectar com SSL", lambda: smtplib.SMTP_SSL(host, porta, timeout=20, context=contexto))
else:
    s = passo("1. Conectar", lambda: smtplib.SMTP(host, porta, timeout=20))
passo("2. Apresentação (EHLO)", s.ehlo)
if seguranca == "starttls":
    passo("3. Conexão segura (STARTTLS)", lambda: s.starttls(context=contexto))
    passo("4. Apresentação de novo (EHLO)", s.ehlo)
passo("5. Login com usuário e senha", lambda: s.login(usuario, senha))

msg = EmailMessage()
msg["Subject"] = "Teste do Sistema de Gestão de Notas Fiscais"
msg["From"] = remetente
msg["To"] = destino
msg.set_content("Se você recebeu este e-mail, o envio está funcionando.")
passo(f"6. Enviar para {destino}", lambda: s.send_message(msg))
s.quit()
print("\nTudo certo: o e-mail saiu. Se não chegar, confira o spam e a quarentena do destino.")
