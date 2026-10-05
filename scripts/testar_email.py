# -*- coding: utf-8 -*-
"""
Testa se o envio de e-mail está funcionando, com as configurações SMTP do .env.

Uso (na pasta raiz do projeto):
    python scripts/testar_email.py seu.email@exemplo.com
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROJETO / ".env")
sys.path.insert(0, str(RAIZ_PROJETO))
from nfe_app.email_envio import enviar_email, email_configurado  # noqa: E402

if len(sys.argv) != 2 or "@" not in sys.argv[1]:
    sys.exit(__doc__)

if not email_configurado():
    sys.exit("[erro] SMTP_HOST não está no .env. Preencha as linhas SMTP_ (veja .env.example).")

try:
    enviar_email(sys.argv[1], "Teste do Sistema de Gestão de Notas Fiscais",
                 "Se você recebeu esta mensagem, o envio de e-mails do sistema está funcionando.")
except RuntimeError as erro:
    sys.exit(f"[erro] {erro}")

print(f"[ok] E-mail de teste enviado para {sys.argv[1]}. Confira a caixa de entrada (e o spam).")
