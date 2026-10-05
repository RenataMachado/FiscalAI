# -*- coding: utf-8 -*-
"""
Gerencia quem pode entrar no sistema (tabela "usuarios") e as senhas, pelo terminal.

O mais prático no dia a dia é a tela "Usuários" dentro do sistema (aprovar pedidos,
gerar nova senha etc.). Este script serve para o PRIMEIRO administrador e para emergências.

Rode sempre a partir da raiz do projeto (ou de qualquer pasta; ele acha o .env sozinho).

Exemplos:
    python scripts/gerenciar_usuarios.py adicionar maria.silva@spaguas.sp.gov.br "Maria Silva" admin
    python scripts/gerenciar_usuarios.py adicionar joao@spaguas.sp.gov.br "João Souza" consulta
    python scripts/gerenciar_usuarios.py senha joao@spaguas.sp.gov.br   (define ou redefine a senha;
                                                                         também desbloqueia a conta)
    python scripts/gerenciar_usuarios.py listar
    python scripts/gerenciar_usuarios.py perfil joao@spaguas.sp.gov.br admin
    python scripts/gerenciar_usuarios.py desativar joao@spaguas.sp.gov.br
    python scripts/gerenciar_usuarios.py ativar joao@spaguas.sp.gov.br
    python scripts/gerenciar_usuarios.py acessos            (últimos 30 acessos)
    python scripts/gerenciar_usuarios.py acessos 100        (últimos 100 acessos)

Perfis:
    admin        -> todas as telas, inclusive Usuários
    processador  -> Processador Nota, Contratos, Aditivos, Empenhos + Balanço e Vigência
    consulta     -> apenas Balanço e Acompanhamento de Vigência
"""
import os
import sys
import getpass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ_PROJETO / ".env")

# Permite importar o pacote nfe_app (onde fica a rotina de senhas) rodando de qualquer pasta
sys.path.insert(0, str(RAIZ_PROJETO))
from nfe_app.senhas import gerar_hash, problema_na_senha  # noqa: E402

PERFIS_VALIDOS = ("admin", "processador", "consulta")


def conectar():
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("[erro] DATABASE_URL não encontrada no .env.")
    return create_engine(url)


def _email(valor):
    email = valor.strip().lower()
    if "@" not in email:
        sys.exit(f"[erro] '{valor}' não parece um e-mail.")
    return email


def _perfil(valor):
    perfil = valor.strip().lower()
    if perfil not in PERFIS_VALIDOS:
        sys.exit(f"[erro] Perfil '{valor}' inválido. Use: {', '.join(PERFIS_VALIDOS)}.")
    return perfil


def adicionar(engine, email, nome, perfil):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO usuarios (email, nome, perfil, ativo, aprovado)
            VALUES (:email, :nome, :perfil, TRUE, TRUE)
            ON CONFLICT (email) DO UPDATE
               SET nome = EXCLUDED.nome, perfil = EXCLUDED.perfil, ativo = TRUE, aprovado = TRUE
        """), {"email": email, "nome": nome, "perfil": perfil})
    print(f"[ok] {email} liberado com perfil '{perfil}'.")
    print(f"     Se ainda não tem senha, defina agora: python scripts/gerenciar_usuarios.py senha {email}")


def definir_senha(engine, email):
    """Pede a senha no terminal (sem mostrar o que é digitado) e salva só o hash."""
    senha = getpass.getpass("Nova senha (não aparece enquanto você digita): ")
    problema = problema_na_senha(senha)
    if problema:
        sys.exit(f"[erro] {problema}")
    if getpass.getpass("Repita a senha: ") != senha:
        sys.exit("[erro] As duas senhas não são iguais. Nada foi alterado.")
    with engine.begin() as conn:
        resultado = conn.execute(text("""
            UPDATE usuarios
               SET senha_hash = :hash, tentativas_falhas = 0, bloqueado_ate = NULL
             WHERE email = :email
        """), {"hash": gerar_hash(senha), "email": email})
    if resultado.rowcount == 0:
        sys.exit(f"[erro] {email} não está cadastrado. Use o comando 'adicionar' primeiro.")
    print(f"[ok] Senha de {email} definida (e conta desbloqueada, se estava bloqueada).")


def alterar(engine, email, campo_sql, valor, mensagem):
    # campo_sql vem SEMPRE de dentro deste script (nunca do usuário), por isso é seguro no texto do SQL
    with engine.begin() as conn:
        resultado = conn.execute(text(f"UPDATE usuarios SET {campo_sql} = :valor WHERE email = :email"),
                                 {"valor": valor, "email": email})
    if resultado.rowcount == 0:
        sys.exit(f"[erro] {email} não está cadastrado.")
    print(f"[ok] {mensagem}")


def listar(engine):
    with engine.connect() as conn:
        linhas = conn.execute(text(
            "SELECT email, nome, perfil, ativo, ultimo_acesso, senha_hash IS NOT NULL AS tem_senha, "
            "       (bloqueado_ate IS NOT NULL AND bloqueado_ate > now()) AS bloqueado, aprovado "
            "FROM usuarios ORDER BY ativo DESC, email"
        )).all()
    if not linhas:
        print("Nenhum usuário cadastrado. Use o comando 'adicionar'.")
        return
    print(f"{'E-MAIL':40} {'NOME':25} {'PERFIL':9} {'ATIVO':6} {'SENHA':10} ÚLTIMO ACESSO")
    for email, nome, perfil, ativo, ultimo, tem_senha, bloqueado, aprovado in linhas:
        ultimo_txt = ultimo.strftime("%d/%m/%Y %H:%M") if ultimo else "-"
        if not aprovado:
            senha_txt = "PEDIDO"
        else:
            senha_txt = "BLOQUEADA" if bloqueado else ("ok" if tem_senha else "SEM SENHA")
        print(f"{email:40} {(nome or '-')[:25]:25} {perfil:9} {'sim' if ativo else 'NÃO':6} {senha_txt:10} {ultimo_txt}")


def acessos(engine, quantidade):
    with engine.connect() as conn:
        linhas = conn.execute(text(
            "SELECT criado_em, email, evento, detalhe FROM registro_acessos ORDER BY criado_em DESC LIMIT :n"
        ), {"n": quantidade}).all()
    if not linhas:
        print("Nenhum acesso registrado ainda.")
        return
    for quando, email, evento, detalhe in linhas:
        alerta = "  <-- ATENÇÃO" if evento in ("login_falhou", "login_bloqueado", "conta_bloqueada",
                                              "usuario_inativo") else ""
        print(f"{quando:%d/%m/%Y %H:%M}  {evento:16} {email or '-':40} {detalhe or ''}{alerta}")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    comando = args[0].lower()
    engine = conectar()

    if comando == "adicionar" and len(args) == 4:
        adicionar(engine, _email(args[1]), args[2].strip(), _perfil(args[3]))
    elif comando == "senha" and len(args) == 2:
        definir_senha(engine, _email(args[1]))
    elif comando == "listar":
        listar(engine)
    elif comando == "perfil" and len(args) == 3:
        perfil = _perfil(args[2])
        alterar(engine, _email(args[1]), "perfil", perfil, f"{args[1]} agora tem perfil '{perfil}'.")
    elif comando == "desativar" and len(args) == 2:
        alterar(engine, _email(args[1]), "ativo", False, f"{args[1]} DESATIVADO (bloqueio vale na próxima interação).")
    elif comando == "ativar" and len(args) == 2:
        alterar(engine, _email(args[1]), "ativo", True, f"{args[1]} reativado.")
    elif comando == "acessos":
        acessos(engine, int(args[1]) if len(args) > 1 else 30)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
