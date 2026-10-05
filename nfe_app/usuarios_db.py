# -*- coding: utf-8 -*-
"""
Todas as consultas ao banco sobre usuários, login e senhas.
Ficam aqui para a tela de login (auth.py) e a tela de administração
(pages/usuarios.py) usarem as mesmas regras.

Sempre com parâmetros (:nome): nada de juntar texto digitado pelo usuário no SQL.
"""
import os

from sqlalchemy import text

from nfe_app.config import engine
from nfe_app.senhas import gerar_hash, gerar_senha_temporaria

# Por quantas horas a senha temporária enviada por e-mail vale (configurável no .env)
HORAS_SENHA_TEMPORARIA = int(os.getenv("LOGIN_HORAS_SENHA_TEMPORARIA", "24"))

# Intervalo mínimo entre dois pedidos de "esqueci a senha" para a mesma conta
# (evita que alguém encha a caixa de e-mail de outra pessoa)
MINUTOS_ENTRE_REDEFINICOES = 5


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def buscar_por_id(usuario_id):
    with engine.connect() as conn:
        linha = conn.execute(
            text("SELECT id, email, nome, perfil, ativo, aprovado FROM usuarios WHERE id = :id"),
            {"id": usuario_id},
        ).mappings().first()
    return dict(linha) if linha else None


def buscar_para_login(email):
    """Dados para conferir o login. A senha temporária só vem se ainda estiver no prazo."""
    with engine.connect() as conn:
        linha = conn.execute(
            text("""
                SELECT id, email, nome, perfil, ativo, aprovado, senha_hash,
                       (bloqueado_ate IS NOT NULL AND bloqueado_ate > now()) AS bloqueado,
                       CASE WHEN senha_temporaria_expira > now()
                            THEN senha_temporaria_hash END AS senha_temporaria_hash
                  FROM usuarios
                 WHERE email = :email
            """),
            {"email": email},
        ).mappings().first()
    return dict(linha) if linha else None


def registrar_senha_errada(usuario_id, maximo, minutos_bloqueio):
    """
    Soma 1 tentativa errada. Ao chegar no limite, bloqueia a conta por alguns minutos
    e zera o contador. Devolve True se a conta acabou de ser bloqueada.
    """
    with engine.begin() as conn:
        linha = conn.execute(
            text("""
                UPDATE usuarios
                   SET tentativas_falhas = CASE WHEN tentativas_falhas + 1 >= :maximo
                                                THEN 0 ELSE tentativas_falhas + 1 END,
                       bloqueado_ate     = CASE WHEN tentativas_falhas + 1 >= :maximo
                                                THEN now() + make_interval(mins => :minutos)
                                                ELSE bloqueado_ate END
                 WHERE id = :id
             RETURNING (bloqueado_ate IS NOT NULL AND bloqueado_ate > now()) AS bloqueou
            """),
            {"id": usuario_id, "maximo": maximo, "minutos": minutos_bloqueio},
        ).mappings().first()
    return bool(linha and linha["bloqueou"])


def registrar_login_ok(usuario_id, apagar_senha_temporaria):
    """
    Zera as tentativas erradas e marca o último acesso.
    Se a pessoa entrou com a senha DE SEMPRE, a temporária (se houver) deixa de valer.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE usuarios
                   SET tentativas_falhas = 0, bloqueado_ate = NULL, ultimo_acesso = now(),
                       senha_temporaria_hash   = CASE WHEN :apagar THEN NULL ELSE senha_temporaria_hash END,
                       senha_temporaria_expira = CASE WHEN :apagar THEN NULL ELSE senha_temporaria_expira END
                 WHERE id = :id
            """),
            {"id": usuario_id, "apagar": bool(apagar_senha_temporaria)},
        )


def registrar_acesso(email, evento, detalhe=""):
    """Grava um evento de auditoria. Nunca derruba o app se o registro falhar."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO registro_acessos (email, evento, detalhe) VALUES (:email, :evento, :detalhe)"),
                {"email": email, "evento": evento, "detalhe": (detalhe or "")[:500]},
            )
    except Exception as erro:
        print(f"[auth] Não foi possível registrar o acesso: {erro}")


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------
def trocar_senha(usuario_id, nova_senha):
    """Salva a senha nova (só o hash) e apaga a temporária."""
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE usuarios
                   SET senha_hash = :hash, senha_temporaria_hash = NULL, senha_temporaria_expira = NULL,
                       tentativas_falhas = 0, bloqueado_ate = NULL
                 WHERE id = :id
            """),
            {"id": usuario_id, "hash": gerar_hash(nova_senha)},
        )


def gerar_senha_temporaria_pelo_admin(usuario_id):
    """
    Usado pelo admin (aprovação e "gerar nova senha"). Também desbloqueia a conta.
    A senha de sempre (se existir) continua valendo até a pessoa criar uma nova.
    Devolve a senha temporária em texto, para ser enviada por e-mail.
    """
    senha = gerar_senha_temporaria()
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE usuarios
                   SET senha_temporaria_hash = :hash,
                       senha_temporaria_expira = now() + make_interval(hours => :horas),
                       senha_temporaria_criada_em = now(),
                       tentativas_falhas = 0, bloqueado_ate = NULL
                 WHERE id = :id
            """),
            {"id": usuario_id, "hash": gerar_hash(senha), "horas": HORAS_SENHA_TEMPORARIA},
        )
    return senha


def gerar_senha_temporaria_esqueci(email):
    """
    Usado no "Esqueci a senha". Só gera para contas aprovadas e ativas, e no máximo
    uma vez a cada poucos minutos. NÃO desbloqueia a conta (senão viraria um jeito
    de continuar tentando adivinhar a senha).
    Devolve (nome, senha_temporaria) ou None se não gerou.
    """
    senha = gerar_senha_temporaria()
    with engine.begin() as conn:
        linha = conn.execute(
            text("""
                UPDATE usuarios
                   SET senha_temporaria_hash = :hash,
                       senha_temporaria_expira = now() + make_interval(hours => :horas),
                       senha_temporaria_criada_em = now()
                 WHERE email = :email AND ativo AND aprovado
                   AND (senha_temporaria_criada_em IS NULL
                        OR senha_temporaria_criada_em < now() - make_interval(mins => :intervalo))
             RETURNING nome
            """),
            {"email": email, "hash": gerar_hash(senha), "horas": HORAS_SENHA_TEMPORARIA,
             "intervalo": MINUTOS_ENTRE_REDEFINICOES},
        ).mappings().first()
    return (linha["nome"], senha) if linha else None


# ---------------------------------------------------------------------------
# Pedidos de acesso
# ---------------------------------------------------------------------------
def criar_pedido(email, nome, motivo):
    """Cria o pedido de acesso (conta inativa, aguardando o admin). False se o e-mail já existia."""
    with engine.begin() as conn:
        linha = conn.execute(
            text("""
                INSERT INTO usuarios (email, nome, perfil, ativo, aprovado, pedido_em, motivo_pedido)
                VALUES (:email, :nome, 'consulta', FALSE, FALSE, now(), :motivo)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
            """),
            {"email": email, "nome": nome, "motivo": motivo},
        ).first()
    return linha is not None


def listar_pendentes():
    with engine.connect() as conn:
        linhas = conn.execute(text("""
            SELECT id, email, nome, motivo_pedido, pedido_em
              FROM usuarios
             WHERE NOT aprovado
             ORDER BY pedido_em
        """)).mappings().all()
    return [dict(l) for l in linhas]


def contar_pendentes():
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM usuarios WHERE NOT aprovado")).scalar() or 0


def aprovar_pedido(usuario_id, perfil):
    """Libera a conta com o perfil escolhido. Devolve {"email", "nome"} ou None se o pedido não existe mais."""
    with engine.begin() as conn:
        linha = conn.execute(
            text("""
                UPDATE usuarios SET aprovado = TRUE, ativo = TRUE, perfil = :perfil
                 WHERE id = :id AND NOT aprovado
             RETURNING email, nome
            """),
            {"id": usuario_id, "perfil": perfil},
        ).mappings().first()
    return dict(linha) if linha else None


def recusar_pedido(usuario_id):
    """Apaga o pedido (a pessoa pode pedir de novo depois). Devolve o e-mail ou None."""
    with engine.begin() as conn:
        linha = conn.execute(
            text("DELETE FROM usuarios WHERE id = :id AND NOT aprovado RETURNING email"),
            {"id": usuario_id},
        ).first()
    return linha[0] if linha else None


# ---------------------------------------------------------------------------
# Administração dos usuários já aprovados
# ---------------------------------------------------------------------------
def criar_usuario_pelo_admin(email, nome, perfil):
    """
    Cadastro feito pelo administrador: a conta já nasce aprovada e ativa.
    Devolve o id da conta nova, ou None se o e-mail já existe no sistema
    (inclusive como pedido de acesso pendente).
    """
    with engine.begin() as conn:
        linha = conn.execute(
            text("""
                INSERT INTO usuarios (email, nome, perfil, ativo, aprovado)
                VALUES (:email, :nome, :perfil, TRUE, TRUE)
                ON CONFLICT (email) DO NOTHING
                RETURNING id
            """),
            {"email": email, "nome": nome, "perfil": perfil},
        ).first()
    return linha[0] if linha else None


def situacao_do_email(email):
    """Para explicar por que um cadastro não foi feito: 'pendente', 'cadastrado' ou None."""
    with engine.connect() as conn:
        linha = conn.execute(text("SELECT aprovado FROM usuarios WHERE email = :email"),
                             {"email": email}).first()
    if linha is None:
        return None
    return "cadastrado" if linha[0] else "pendente"
def listar_usuarios():
    with engine.connect() as conn:
        linhas = conn.execute(text("""
            SELECT id, email, nome, perfil, ativo, ultimo_acesso,
                   senha_hash IS NOT NULL AS tem_senha,
                   (senha_temporaria_expira IS NOT NULL AND senha_temporaria_expira > now()) AS tem_temporaria,
                   (bloqueado_ate IS NOT NULL AND bloqueado_ate > now()) AS bloqueado
              FROM usuarios
             WHERE aprovado
             ORDER BY ativo DESC, nome NULLS LAST, email
        """)).mappings().all()
    return [dict(l) for l in linhas]


def alterar_perfil(usuario_id, perfil):
    with engine.begin() as conn:
        conn.execute(text("UPDATE usuarios SET perfil = :perfil WHERE id = :id"),
                     {"id": usuario_id, "perfil": perfil})


def alterar_ativo(usuario_id, ativo):
    with engine.begin() as conn:
        conn.execute(text("UPDATE usuarios SET ativo = :ativo WHERE id = :id"),
                     {"id": usuario_id, "ativo": bool(ativo)})
