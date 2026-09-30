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

from nfe_app.pages.processar_nota import processa_nota
from nfe_app.pages.balanco import balanco_nota_fiscal
from nfe_app.pages.contratos import gerenciar_contratos
from nfe_app.pages.aditivos import gerenciar_aditivos
from nfe_app.pages.empenhos import gerenciar_empenhos
from nfe_app.pages.vigencia import acompanhamento_contratos

# Pasta onde está este arquivo. Assim as imagens são encontradas
# mesmo que você rode o comando a partir de outra pasta.
PASTA_BASE = Path(__file__).resolve().parent
LOGO_ESCURO = PASTA_BASE / "images" / "SP-4.png"    # usado no tema escuro
LOGO_CLARO = PASTA_BASE / "images" / "SP-4-P.png"   # usado no tema claro

# Cada página: (texto do botão, nome interno, função que desenha a tela)
PAGINAS = [
    ("📄 Processador Nota", "Processar Nota", processa_nota),
    ("📊 Balanço", "Balanço (Painel de Controle)", balanco_nota_fiscal),
    ("📑 Resumos Contratuais", "Resumos Contratuais", gerenciar_contratos),
    ("➕ Termos Aditivos", "Termos Aditivos", gerenciar_aditivos),
    ("🧾 Notas de Empenho", "Notas de Empenho", gerenciar_empenhos),
    ("⏱️ Acompanhamento de Vigência", "Acompanhamento Vigência", acompanhamento_contratos),
]


def detectar_tema_escuro():
    """
    Descobre se o Streamlit está no tema escuro.
    Se o pacote streamlit-theme não estiver instalado ou der erro,
    o app continua funcionando (usa o logo do tema escuro por padrão).
    """
    try:
        from streamlit_theme import st_theme
        tema = st_theme()
        if tema:
            return tema.get("base") == "dark"
    except Exception:
        pass
    try:
        return st.get_option("theme.base") != "light"
    except Exception:
        return True


def main():
    st.set_page_config(page_title="Leitor NFe Tabular", layout="wide")

    caminho_logo = LOGO_ESCURO if detectar_tema_escuro() else LOGO_CLARO

    col1, col2 = st.columns([5, 1])
    with col1:
        st.title("Sistema de Gestão de Notas Fiscais")
    with col2:
        st.write("")
        st.write("")
        if caminho_logo.exists():
            st.image(str(caminho_logo), width=150)

    if 'pagina_atual' not in st.session_state:
        st.session_state['pagina_atual'] = PAGINAS[0][1]

    st.sidebar.subheader("Navegação")
    for rotulo, nome, _ in PAGINAS:
        if st.sidebar.button(rotulo, use_container_width=True, key=f"nav_{nome}"):
            st.session_state['pagina_atual'] = nome

    st.sidebar.divider()

    for _, nome, funcao_pagina in PAGINAS:
        if st.session_state['pagina_atual'] == nome:
            funcao_pagina()
            break


if __name__ == "__main__":
    main()
