# -*- coding: utf-8 -*-
"""
Ponto de entrada do Streamlit.

Rode com:
    streamlit run app.py

Este arquivo fica FORA do pacote nfe_app/ de propósito: assim os imports
absolutos dentro do pacote (from nfe_app.xxx import yyy) funcionam sem
problemas de "relative import" ao executar via `streamlit run`.
"""
from pathlib import Path

import streamlit as st

from nfe_app import tema
from nfe_app.auth import exigir_login, mostrar_usuario_na_barra_lateral, pagina_minha_senha
from nfe_app.pages.processar_nota import processa_nota
from nfe_app.pages.balanco import balanco_nota_fiscal
from nfe_app.pages.contratos import gerenciar_contratos
from nfe_app.pages.aditivos import gerenciar_aditivos
from nfe_app.pages.empenhos import gerenciar_empenhos
from nfe_app.pages.vigencia import acompanhamento_contratos
from nfe_app.pages.usuarios import gerenciar_usuarios

# Pasta onde está este arquivo. Assim as imagens são encontradas
# mesmo que você rode o comando a partir de outra pasta.
PASTA_BASE = Path(__file__).resolve().parent
LOGO_BRANCO = PASTA_BASE / "images" / "SP-4.png"     # para fundos escuros (barra lateral e tela de entrada)
LOGO_COLORIDO = PASTA_BASE / "images" / "SP-4-P.png" # para fundos claros

# Cada página: (texto do botão, nome interno, função que desenha a tela, perfis que podem ver)
#   admin       -> tudo, inclusive a tela Usuários
#   processador -> processa notas, contratos, aditivos e empenhos + Balanço e Vigência
#   consulta    -> só Balanço e Vigência
TODOS = ("admin", "processador", "consulta")
PROCESSAMENTO = ("admin", "processador")
SO_ADMIN = ("admin",)
PAGINAS = [
    ("📄 Processador Nota", "Processar Nota", processa_nota, PROCESSAMENTO),
    ("📊 Balanço", "Balanço (Painel de Controle)", balanco_nota_fiscal, TODOS),
    ("📑 Resumos Contratuais", "Resumos Contratuais", gerenciar_contratos, PROCESSAMENTO),
    ("➕ Termos Aditivos", "Termos Aditivos", gerenciar_aditivos, PROCESSAMENTO),
    ("🧾 Notas de Empenho", "Notas de Empenho", gerenciar_empenhos, PROCESSAMENTO),
    ("⏱️ Acompanhamento de Vigência", "Acompanhamento Vigência", acompanhamento_contratos, TODOS),
    ("👥 Usuários", "Usuários", gerenciar_usuarios, SO_ADMIN),
    ("🔑 Minha senha", "Minha senha", pagina_minha_senha, TODOS),
]


def _ir_para_pagina(nome):
    st.session_state["pagina_atual"] = nome


def main():
    st.set_page_config(page_title="Gestão de Notas Fiscais · SP Águas", page_icon="🧾", layout="wide")

    # Cores, fontes e detalhes no padrão da apresentação da SP Águas (veja nfe_app/tema.py)
    tema.aplicar_tema()

    # LOGIN: se a pessoa ainda não entrou (ou foi desativada), esta função
    # mostra a tela de login e PARA o app aqui. Nada abaixo roda sem login.
    usuario = exigir_login(logo=LOGO_BRANCO)

    # Só as páginas que o perfil desta pessoa pode ver
    paginas_permitidas = [p for p in PAGINAS if usuario["perfil"] in p[3]]
    nomes_permitidos = [p[1] for p in paginas_permitidas]
    # Se a página guardada não é permitida para este perfil, volta para a primeira permitida
    if st.session_state.get("pagina_atual") not in nomes_permitidos:
        st.session_state["pagina_atual"] = nomes_permitidos[0]

    # Barra lateral: logo, usuário e navegação (a página atual fica destacada)
    if LOGO_BRANCO.exists():
        st.sidebar.image(str(LOGO_BRANCO), width=150)
    mostrar_usuario_na_barra_lateral(usuario)
    st.sidebar.divider()
    tema.rotulo_lateral("Navegação")
    for rotulo, nome, _, _ in paginas_permitidas:
        atual = st.session_state["pagina_atual"] == nome
        st.sidebar.button(rotulo, use_container_width=True, key=f"nav_{nome}",
                          type="primary" if atual else "secondary",
                          on_click=_ir_para_pagina, args=(nome,))

    # Topo das páginas, como nos slides
    tema.topo_da_pagina("Gestão de Notas Fiscais")

    # Só executa páginas da lista PERMITIDA (dupla checagem do perfil)
    for _, nome, funcao_pagina, _ in paginas_permitidas:
        if st.session_state["pagina_atual"] == nome:
            tema.rotulo(nome)  # só o nome da página, sem número
            funcao_pagina()
            break


if __name__ == "__main__":
    main()
