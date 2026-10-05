# -*- coding: utf-8 -*-
"""
Guarda e confere senhas com segurança, usando só a biblioteca padrão do Python.

A senha NUNCA é salva como foi digitada. O banco guarda um "hash": uma espécie de
impressão digital calculada a partir da senha + um "sal" aleatório, repetida
centenas de milhares de vezes (algoritmo PBKDF2-SHA256). Assim, mesmo quem
conseguir ler o banco não descobre as senhas, e duas pessoas com a mesma senha
ficam com hashes diferentes.

Formato salvo no banco:  pbkdf2_sha256$600000$<sal>$<hash>
"""
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 600_000      # quanto maior, mais difícil (e lento) adivinhar a senha por força bruta
TAMANHO_MINIMO = 8


def _calcular(senha, sal_hex, iteracoes):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal_hex), iteracoes).hex()


def gerar_hash(senha):
    """Transforma a senha no texto que vai para o banco (coluna senha_hash)."""
    sal = secrets.token_hex(16)
    return f"{ALGORITMO}${ITERACOES}${sal}${_calcular(senha, sal, ITERACOES)}"


def conferir_senha(senha, hash_salvo):
    """True se a senha digitada corresponde ao hash guardado no banco."""
    try:
        algoritmo, iteracoes, sal, esperado = hash_salvo.split("$")
        if algoritmo != ALGORITMO:
            return False
        # compare_digest compara sem "vazar" pelo tempo de resposta quantos caracteres bateram
        return hmac.compare_digest(_calcular(senha, sal, int(iteracoes)), esperado)
    except (ValueError, AttributeError):
        return False


def problema_na_senha(senha):
    """Devolve o motivo se a senha for fraca demais, ou None se estiver ok."""
    if len(senha) < TAMANHO_MINIMO:
        return f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres."
    if senha.strip() != senha:
        return "A senha não pode começar nem terminar com espaço."
    return None


# Letras e números sem os que se confundem na leitura (0/O, 1/l/I)
ALFABETO_TEMPORARIA = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


def gerar_senha_temporaria(tamanho=12):
    """Senha aleatória para mandar por e-mail (a pessoa troca no primeiro acesso)."""
    return "".join(secrets.choice(ALFABETO_TEMPORARIA) for _ in range(tamanho))


# Hash de uma senha aleatória que ninguém sabe. Usado quando alguém digita um e-mail
# que não existe: o sistema confere a senha contra ele mesmo assim, para a resposta
# demorar o mesmo tempo e não denunciar quais e-mails estão cadastrados.
HASH_FALSO = gerar_hash(secrets.token_hex(16))
