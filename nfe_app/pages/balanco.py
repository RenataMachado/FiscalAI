"""
Pagina: Balanco (Painel de Controle) -- visao consolidada das notas fiscais e exportacoes.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from nfe_app.config import engine
from nfe_app.formatters import formata_valor, formata_cnpj, formata_data
from nfe_app.excel_export import gerar_excel_levantamento, gerar_excel_calculo_pagto
from nfe_app.pdf_export import gerar_pdf_balanco

def balanco_nota_fiscal():
    st.header("📈 Balanço de Notas Fiscais")
    try:
        df_notas = pd.read_sql_table('notas_fiscais', con=engine)
        try:
            df_contratos = pd.read_sql_table('resumo_contratos', con=engine)
        except Exception:
            df_contratos = pd.DataFrame(columns=['numero_contrato', 'numero_contrato_spaguas', 'processo_sei'])

        try:
            df_nes = pd.read_sql_table('notas_empenho', con=engine)
        except Exception:
            df_nes = pd.DataFrame(columns=['numero_ne', 'processo_sei', 'natureza_despesa', 'fonte_recurso'])

        if df_notas.empty:
            st.info("Nenhuma nota fiscal registrada no banco ainda.")
            return

        if 'numero_contrato' not in df_notas.columns:
            df_notas['numero_contrato'] = "N/A"

        if not df_contratos.empty and 'numero_contrato' in df_contratos.columns:
            cols_merge = ['numero_contrato']
            if 'numero_contrato_spaguas' in df_contratos.columns:
                cols_merge.append('numero_contrato_spaguas')
            if 'processo_sei' in df_contratos.columns:
                cols_merge.append('processo_sei')
                
            df_contratos_unicos = df_contratos[cols_merge].drop_duplicates(subset=['numero_contrato'])
            df = pd.merge(df_notas, df_contratos_unicos, on='numero_contrato', how='left')
        else:
            df = df_notas.copy()

        if not df_nes.empty and 'processo_sei' in df_nes.columns:
            cols_nes = ['processo_sei', 'numero_ne', 'natureza_despesa', 'fonte_recurso']
            if 'ug' in df_nes.columns: cols_nes.append('ug')
            if 'assunto' in df_nes.columns: cols_nes.append('assunto')
                
            df_nes_unicas = df_nes[cols_nes].drop_duplicates(subset=['processo_sei'])
            df = pd.merge(df, df_nes_unicas, on='processo_sei', how='left', suffixes=('', '_ne'))
        else:
            df['numero_ne'] = "-"
            df['natureza_despesa'] = "-"
            df['fonte_recurso'] = "-"
            df['ug'] = ""
            df['assunto'] = ""

        if 'numero_contrato_spaguas' not in df.columns: df['numero_contrato_spaguas'] = ""
        if 'processo_sei' not in df.columns: df['processo_sei'] = ""
        if 'numero_ne' not in df.columns: df['numero_ne'] = "-"
        if 'natureza_despesa' not in df.columns: df['natureza_despesa'] = "-"
        if 'fonte_recurso' not in df.columns: df['fonte_recurso'] = "-"
        if 'ug' not in df.columns: df['ug'] = ""
        if 'assunto' not in df.columns: df['assunto'] = ""

        st.sidebar.subheader("Filtros")
        emissor_filtro = st.sidebar.multiselect("Filtrar por CNPJ do Emitente", options=df['cnpj_emitente'].unique())
        empresa_filtro = st.sidebar.multiselect("Filtrar por Nome da Empresa", options=df['Arquivo'].unique())
        
        if emissor_filtro: df = df[df['cnpj_emitente'].isin(emissor_filtro)]
        if empresa_filtro: df = df[df['Arquivo'].isin(empresa_filtro)]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Valor Total Bruto", formata_valor(df['valor_total'].sum()))
        col2.metric("Total Impostos Retidos", formata_valor(df['valor_ir'].sum()))
        col3.metric("Valor Total Líquido", formata_valor(df['valor_liquido'].sum()))
        
        st.divider()
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            df_faturamento = df.groupby('Arquivo')['valor_total'].sum().reset_index()
            fig1 = px.bar(df_faturamento, x='valor_total', y='Arquivo', orientation='h',
                          title="Faturamento Bruto por Empresa",
                          labels={'Arquivo': 'Empresa', 'valor_total': 'Faturamento (R$)'},
                          color_discrete_sequence=['#005b96'])
            fig1.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            df_impostos = df.groupby('Arquivo')['valor_ir'].sum().reset_index()
            df_impostos = df_impostos[df_impostos['valor_ir'] > 0]
            fig2 = px.bar(df_impostos, x='valor_ir', y='Arquivo', orientation='h',
                          title="Impostos Retidos (IR) por Empresa",
                          labels={'Arquivo': 'Empresa', 'valor_ir': 'Imposto Retido (R$)'},
                          color_discrete_sequence=['#d62728'])
            fig2.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig2, use_container_width=True)
            
        st.divider()
        st.write("### Detalhamento das Notas")
        df['cnpj_emitente'] = df['cnpj_emitente'].apply(formata_cnpj)
        df['data_emissao'] = df['data_emissao'].apply(formata_data)
        df['vencimento'] = df['vencimento'].apply(formata_data)
        df['numero_contrato'] = df['numero_contrato'].apply(lambda x: x if x else "N/A")
        df['numero_contrato_spaguas'] = df['numero_contrato_spaguas'].apply(lambda x: x if pd.notna(x) and x != "" else "-")
        df['processo_sei'] = df['processo_sei'].apply(lambda x: x if pd.notna(x) and x != "" else "-")
        df['numero_ne'] = df['numero_ne'].apply(lambda x: x if pd.notna(x) and x != "" else "-")
        df['natureza_despesa'] = df['natureza_despesa'].apply(lambda x: x if pd.notna(x) and x != "" else "-")
        df['fonte_recurso'] = df['fonte_recurso'].apply(lambda x: x if pd.notna(x) and x != "" else "-")
        
        st.dataframe(
            df[['Arquivo', 'numero_nfe', 'numero_ne', 'natureza_despesa', 'fonte_recurso', 'numero_contrato', 'numero_contrato_spaguas', 'processo_sei', 'data_emissao', 'vencimento', 'cnpj_emitente', 'valor_total', 'valor_iss', 'valor_ir', 'valor_liquido']], 
            use_container_width=True, hide_index=True,
            column_config={
                "Arquivo": st.column_config.TextColumn("Nome da Empresa"),
                "numero_nfe": st.column_config.TextColumn("NFE"),
                "numero_ne": st.column_config.TextColumn("Número da NE"),
                "natureza_despesa": st.column_config.TextColumn("Nat. Despesa"),
                "fonte_recurso": st.column_config.TextColumn("Fonte Recurso"),
                "numero_contrato": st.column_config.TextColumn("Contrato"),
                "numero_contrato_spaguas": st.column_config.TextColumn("Contrato SP Águas"),
                "processo_sei": st.column_config.TextColumn("Processo SEI"),
                "data_emissao": st.column_config.TextColumn("Emissão"),
                "vencimento": st.column_config.TextColumn("Vencimento"),
                "cnpj_emitente": st.column_config.TextColumn("CNPJ Emitente"),
                "valor_total": st.column_config.NumberColumn("Valor Bruto", format="R$ %.2f"),
                "valor_iss": st.column_config.NumberColumn("Valor ISS", format="R$ %.2f"), 
                "valor_ir": st.column_config.NumberColumn("Valor IR", format="R$ %.2f"),
                "valor_liquido": st.column_config.NumberColumn("Valor Líquido", format="R$ %.2f")
            }
        )
        
        st.divider()
        st.subheader("📥 Central de Downloads e Relatórios")
        
        dados_para_excel = df.to_dict('records')
        buffer_excel_lev = gerar_excel_levantamento(dados_para_excel)
        buffer_pdf = gerar_pdf_balanco(dados_para_excel)
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📊 Baixar Planilha de Levantamento de Notas",
                data=buffer_excel_lev,
                file_name="levantamento_notas_fiscais.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_dl2:
            st.download_button(
                label="📄 Baixar Relatório em PDF",
                data=buffer_pdf,
                file_name="balanco_notas_fiscais.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.write("")
        st.write("#### 🧮 Gerar Planilha de Cálculo para Pagto (por Processo SEI)")
        
        lista_processos_sei = [p for p in df['processo_sei'].unique() if p and p != "-"]
        
        if lista_processos_sei:
            sei_escolhido = st.selectbox("Selecione o Processo SEI desejado:", lista_processos_sei)
            
            buffer_excel_calc_especifico = gerar_excel_calculo_pagto(dados_para_excel, processo_sei_filtro=sei_escolhido)
            
            st.download_button(
                label=f"📥 Baixar Cálculo para Pagto (SEI: {sei_escolhido})",
                data=buffer_excel_calc_especifico,
                file_name=f"calculo_pagamento_sei_{sei_escolhido.replace('/', '_').replace('.', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.info("ℹ️ Nenhum Processo SEI vinculado às notas atualmente para gerar o cálculo individualizado.")
            
    except Exception as e:
        st.warning(f"Ocorreu um erro ao carregar os dados ou gerar os botões: {e}")
