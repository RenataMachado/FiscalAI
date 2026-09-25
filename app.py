# -*- coding: utf-8 -*-
"""
Ponto de entrada do Streamlit.

Rode com:
    streamlit run app.py

Este arquivo fica FORA do pacote nfe_app/ de propósito: assim os imports
absolutos dentro do pacote (from nfe_app.xxx import yyy) funcionam sem
problemas de "relative import" ao executar via `streamlit run`.
"""
import streamlit as st
from streamlit_theme import st_theme

from nfe_app.pages.processar_nota import processa_nota
from nfe_app.pages.balanco import balanco_nota_fiscal
from nfe_app.pages.contratos import gerenciar_contratos
from nfe_app.pages.aditivos import gerenciar_aditivos
from nfe_app.pages.empenhos import gerenciar_empenhos
from nfe_app.pages.vigencia import acompanhamento_contratos


def main():
    st.set_page_config(page_title="Leitor NFe Tabular", layout="wide")
    theme = st_theme()
    if theme and theme.get("base") == "dark":
        caminho_logo = "images/SP-4.png"   
    else:
        caminho_logo = "images/SP-4-P.png" 
        
    col1, col2 = st.columns([5, 1]) 
    with col1:
        st.title("Sistema de Gestão de Notas Fiscais")
    with col2:
        st.write("")
        st.write("")
        try:
            st.image(caminho_logo, width=150) 
        except:
            pass 
        
    if 'pagina_atual' not in st.session_state:
        st.session_state['pagina_atual'] = "Processar Nota"
        
    st.sidebar.subheader("Navegação")
    if st.sidebar.button("📄 Processador Nota", use_container_width=True):
        st.session_state['pagina_atual'] = "Processar Nota"
    if st.sidebar.button("📊 Balanço ", use_container_width=True):
        st.session_state['pagina_atual'] = "Balanço (Painel de Controle)"
    if st.sidebar.button("📑 Resumos Contratuais", use_container_width=True):
        st.session_state['pagina_atual'] = "Resumos Contratuais"
    if st.sidebar.button("➕ Termos Aditivos", use_container_width=True):
        st.session_state['pagina_atual'] = "Termos Aditivos"
    if st.sidebar.button("🧾 Notas de Empenho", use_container_width=True):
        st.session_state['pagina_atual'] = "Notas de Empenho"
    if st.sidebar.button("⏱️ Acompanhamento de Vigência", use_container_width=True):
        st.session_state['pagina_atual'] = "Acompanhamento Vigência"
        
    st.sidebar.divider() 
    
    if st.session_state['pagina_atual'] == "Processar Nota":
        processa_nota()
    elif st.session_state['pagina_atual'] == "Balanço (Painel de Controle)":
        balanco_nota_fiscal()
    elif st.session_state['pagina_atual'] == "Resumos Contratuais":
        gerenciar_contratos() 
    elif st.session_state['pagina_atual'] == "Termos Aditivos":
        gerenciar_aditivos()
    elif st.session_state['pagina_atual'] == "Notas de Empenho":
        gerenciar_empenhos()
    elif st.session_state['pagina_atual'] == "Acompanhamento Vigência":
        acompanhamento_contratos() 

if __name__ == "__main__":
    main()
