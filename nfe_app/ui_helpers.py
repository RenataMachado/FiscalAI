"""
Funções de apoio à interface: alerta central e persistência de notas fiscais no banco de dados.
"""
import streamlit as st
import pandas as pd

from nfe_app.config import engine

@st.dialog("Resumo do Banco de Dados")
def exibir_alerta_central(total_lido, notas_salvas, erro=None):
    if erro:
        st.error(f"❌ Erro ao salvar no banco: {erro}")
    elif notas_salvas == 0:
        st.warning(f"⚠️ Atenção: Nenhuma nota nova salva. Todas as {total_lido} notas processadas já existem no banco de dados!")
    else:
        duplicadas = total_lido - notas_salvas
        if duplicadas > 0:
            st.success(f"✅ {notas_salvas} nota(s) armazenada(s) com sucesso!")
            st.info(f"ℹ️ {duplicadas} nota(s) ignorada(s) por já existirem no banco.")
        else:
            st.success(f"✅ Todas as {notas_salvas} nota(s) foram armazenadas com sucesso!")
    
    if st.button("OK, Fechar"):
        if 'dados_extraidos' in st.session_state:
            del st.session_state['dados_extraidos']
            
        if 'chave_uploader_notas' in st.session_state:
            st.session_state['chave_uploader_notas'] += 1
            
        st.rerun()

def armazena_info(lista_dados_finais):
    try:
        df_para_salvar = pd.DataFrame(lista_dados_finais)
        total_lido = len(df_para_salvar)
        
        for col in ['data_emissao', 'vencimento']:
            if col in df_para_salvar.columns:
                df_para_salvar[col] = pd.to_datetime(df_para_salvar[col], format='%d/%m/%Y', errors='coerce').dt.strftime('%Y-%m-%d')
                
        for col in ['cnpj_emitente', 'cnpj_pagador']:
            if col in df_para_salvar.columns:
                df_para_salvar[col] = df_para_salvar[col].astype(str).str.replace(r'\D', '', regex=True)

        try:
            df_existente = pd.read_sql('SELECT numero_nfe, cnpj_emitente FROM notas_fiscais', con=engine)
            if not df_existente.empty:
                chave_nfe_existente = df_existente['numero_nfe'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                chave_nfe_nova = df_para_salvar['numero_nfe'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
                
                df_existente['chave'] = chave_nfe_existente + df_existente['cnpj_emitente'].astype(str).str.replace(r'\D', '', regex=True)
                df_para_salvar['chave'] = chave_nfe_nova + df_para_salvar['cnpj_emitente'].astype(str).str.replace(r'\D', '', regex=True)
                
                df_para_salvar = df_para_salvar[~df_para_salvar['chave'].isin(df_existente['chave'])]
                df_para_salvar = df_para_salvar.drop(columns=['chave'])
        except Exception:
            pass
            
        if df_para_salvar.empty:
            exibir_alerta_central(total_lido, 0)
            return

        df_para_salvar.to_sql('notas_fiscais', con=engine, if_exists='append', index=False)
        
        st.balloons()
        exibir_alerta_central(total_lido, len(df_para_salvar))
        
    except Exception as e:
        exibir_alerta_central(0, 0, erro=e)
