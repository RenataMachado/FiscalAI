"""
Pagina: Acompanhamento de Vigencia -- status e alertas de vencimento dos contratos.
"""
import streamlit as st
import pandas as pd
import plotly.express as px

from nfe_app.config import engine
from nfe_app.formatters import formata_valor

def acompanhamento_contratos():
    st.header("📊 Execução e Saldo de Contratos")
    st.markdown("Acompanhe o quanto do valor total de cada contrato (já somado aos aditivos) foi consumido pelas **notas fiscais pagas (vencidas)**.")
    
    try:
        df_notas = pd.read_sql_table('notas_fiscais', con=engine)
        df_contratos = pd.read_sql_table('resumo_contratos', con=engine)
        try:
            df_aditivos = pd.read_sql_table('termos_aditivos', con=engine)
        except Exception:
            df_aditivos = pd.DataFrame(columns=['numero_contrato', 'numero_contrato_spaguas', 'valor_aditivo', 'vigencia_aditivo'])
    except Exception:
        st.info("⚠️ Faça o upload de notas fiscais e do resumo contratual para visualizar esta página.")
        return

    if df_notas.empty or df_contratos.empty:
        st.warning("⚠️ Faltam dados base no banco. Certifique-se de que já salvou notas e contratos.")
        return

    if 'numero_contrato' not in df_contratos.columns or 'valor_contrato' not in df_contratos.columns:
        st.error("❌ A sua planilha de contratos precisa conter as colunas obrigatórias.")
        return

    try:
        if not df_aditivos.empty and 'numero_contrato' in df_aditivos.columns:
            df_soma_adic = df_aditivos.groupby('numero_contrato').agg(
                soma_valor_aditivo=('valor_aditivo', 'sum'),
                soma_meses_aditivo=('vigencia_aditivo', 'sum')
            ).reset_index()
            df_contratos = pd.merge(df_contratos, df_soma_adic, on='numero_contrato', how='left')
        else:
            df_contratos['soma_valor_aditivo'] = 0.0
            df_contratos['soma_meses_aditivo'] = 0

        df_contratos['soma_valor_aditivo'] = df_contratos['soma_valor_aditivo'].fillna(0)
        df_contratos['soma_meses_aditivo'] = df_contratos['soma_meses_aditivo'].fillna(0)
        df_contratos['valor_contrato'] = df_contratos['valor_contrato'] + df_contratos['soma_valor_aditivo']
        df_contratos['vigencia_contrato'] = df_contratos['vigencia_contrato'] + df_contratos['soma_meses_aditivo']

        df_notas['vencimento_dt'] = pd.to_datetime(df_notas['vencimento'], errors='coerce')
        hoje = pd.Timestamp.now().normalize()
        df_pagas = df_notas[df_notas['vencimento_dt'] <= hoje]
        
        df_gasto = df_pagas.groupby(['numero_contrato', 'Arquivo'])['valor_total'].sum().reset_index()
        df_gasto.rename(columns={'valor_total': 'valor_consumido'}, inplace=True)
        
        df_cruzado = pd.merge(df_contratos, df_gasto, on='numero_contrato', how='left')
        df_cruzado['valor_consumido'] = df_cruzado['valor_consumido'].fillna(0)
        df_cruzado['Arquivo'] = df_cruzado['Arquivo'].fillna('Aguardando Notas')
        
        if 'numero_contrato_spaguas' in df_cruzado.columns:
            df_cruzado['Rotulo_Busca'] = df_cruzado.apply(lambda row: f"{row['numero_contrato']} | {row['numero_contrato_spaguas']} ({row['Arquivo']})" if pd.notna(row['numero_contrato_spaguas']) and row['numero_contrato_spaguas'] != "" else f"{row['numero_contrato']} ({row['Arquivo']})", axis=1)
        else:
            df_cruzado['Rotulo_Busca'] = df_cruzado['numero_contrato'].astype(str) + " (" + df_cruzado['Arquivo'].astype(str) + ")"
        
        df_cruzado['saldo_restante'] = df_cruzado['valor_contrato'] - df_cruzado['valor_consumido']
        df_cruzado['% consumido'] = (df_cruzado['valor_consumido'] / df_cruzado['valor_contrato']) * 100
        
        st.subheader("Painel de Alertas")
        contratos_alerta = df_cruzado[df_cruzado['% consumido'] >= 80]
        if not contratos_alerta.empty:
            for _, row in contratos_alerta.iterrows():
                st.error(f"🚨 **ALERTA:** O contrato **{row['numero_contrato']}** ({row['Arquivo']}) já consumiu **{row['% consumido']:.1f}%** do limite! Saldo restante: {formata_valor(row['saldo_restante'])}")
        else:
            st.success("✅ Todos os contratos estão dentro da margem de segurança (abaixo de 80% consumido).")

        st.divider()
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.write("### Percentual de Conclusão")
            contrato_alvo = st.selectbox("Selecione o Contrato e Empresa para visualizar:", df_cruzado['Rotulo_Busca'].unique())
            if contrato_alvo:
                dados_contrato = df_cruzado[df_cruzado['Rotulo_Busca'] == contrato_alvo].iloc[0]
                df_pizza = pd.DataFrame({
                    'Status': ['Executado', 'Saldo'],
                    'Valores': [dados_contrato['valor_consumido'], dados_contrato['saldo_restante']]
                })
                if dados_contrato['saldo_restante'] < 0:
                    df_pizza.loc[1, 'Valores'] = 0 
                
                fig = px.pie(
                    df_pizza, values='Valores', names='Status', hole=0.45, 
                    title=f" {dados_contrato['numero_contrato']}", color='Status',
                    color_discrete_map={'Executado': '#d62728', 'Saldo': '#2ca02c'}
                )
                fig.update_traces(textinfo='percent+label', textfont_size=14)
                st.plotly_chart(fig, use_container_width=True)

        st.write("### Detalhamento Financeiro")
        df_view = df_cruzado.copy()
        for col in ['valor_contrato', 'valor_consumido', 'saldo_restante']:
            df_view[col] = df_view[col].apply(formata_valor)
        df_view['% consumido'] = df_view['% consumido'].apply(lambda x: f"{x:.2f}%")
        
        cols_view = ['numero_contrato']
        if 'numero_contrato_spaguas' in df_view.columns: cols_view.append('numero_contrato_spaguas')
        cols_view.extend(['Arquivo', 'valor_contrato', 'valor_consumido', 'saldo_restante', '% consumido'])
        
        st.dataframe(
            df_view[cols_view], 
            use_container_width=True, hide_index=True,
            column_config={
                "numero_contrato": st.column_config.TextColumn("Contrato (PRODESP)"),
                "numero_contrato_spaguas": st.column_config.TextColumn("Contrato (SP Águas)"),
                "Arquivo": st.column_config.TextColumn("Empresa Vinculada"),
                "valor_contrato": st.column_config.TextColumn("Valor Total (c/ Aditivos)"),
                "valor_consumido": st.column_config.TextColumn("Gasto (Pago)"),
                "saldo_restante": st.column_config.TextColumn("Saldo Restante"),
                "% consumido": st.column_config.TextColumn("% Gasto")
            }
        )

        st.divider()
        st.subheader("⏱️ Acompanhamento do Tempo de Vigência do Contrato")
        df_tempo_notas = df_notas.groupby('numero_contrato').agg(primeiro_vencimento=('vencimento_dt', 'min')).reset_index()
        df_vigencia_calc = pd.merge(df_contratos, df_tempo_notas, on='numero_contrato', how='inner')
        
        if not df_vigencia_calc.empty:
            contrato_escolhido = st.selectbox("Selecione o Contrato para ver a linha do tempo de vigência:", df_vigencia_calc['numero_contrato'].unique(), key="selectbox_tempo_vigencia")
            if contrato_escolhido:
                dados_c = df_vigencia_calc[df_vigencia_calc['numero_contrato'] == contrato_escolhido].iloc[0]
                vigencia_meses = int(dados_c['vigencia_contrato']) if 'vigencia_contrato' in dados_c and pd.notna(dados_c['vigencia_contrato']) else 0
                primeiro_venc = dados_c['primeiro_vencimento']
                
                if pd.notna(primeiro_venc) and vigencia_meses > 0:
                    data_fim_contrato = primeiro_venc + pd.DateOffset(months=vigencia_meses)
                    tempo_total_dias = (data_fim_contrato - primeiro_venc).days
                    tempo_decorrido_dias = (hoje - primeiro_venc).days
                    
                    if tempo_total_dias > 0:
                        porcentagem_decorrida = min(max((tempo_decorrido_dias / tempo_total_dias) * 100, 0), 100)
                    else:
                        porcentagem_decorrida = 0
                        
                    porcentagem_restante = 100 - porcentagem_decorrida
                    
                    def formatar_meses_dias(total_dias):
                        if total_dias <= 0: return "0 dias"
                        meses = int(total_dias // 30)
                        dias = int(total_dias % 30)
                        
                        partes = []
                        if meses > 0:
                            partes.append(f"{meses} mês" if meses == 1 else f"{meses} meses")
                        if dias > 0:
                            partes.append(f"{dias} dia" if dias == 1 else f"{dias} dias")
                        
                        return " e ".join(partes) if partes else "0 dias"

                    tempo_decorrido_real = max(tempo_decorrido_dias, 0)
                    tempo_restante_real = max(tempo_total_dias - tempo_decorrido_dias, 0)
                    
                    texto_decorrido = formatar_meses_dias(tempo_decorrido_real)
                    texto_restante = formatar_meses_dias(tempo_restante_real)
                    
                    col_t1, col_t2, col_t3 = st.columns(3)
                    col_t1.metric("Início (1º Vencimento)", primeiro_venc.strftime('%d/%m/%Y'))
                    col_t2.metric("Fim Previsto (Com Aditivos)", data_fim_contrato.strftime('%d/%m/%Y'))
                    col_t3.metric("Tempo Restante", f"{porcentagem_restante:.1f}%", delta=f"{porcentagem_decorrida:.1f}% decorrido")
                    
                    df_barra = pd.DataFrame({
                        'Fase': ['Tempo Decorrido', 'Tempo Restante'],
                        'Dias': [tempo_decorrido_real, tempo_restante_real],
                        'Label': [texto_decorrido, texto_restante]
                    })
                    
                    fig_tempo = px.bar(
                        df_barra, x='Dias', y='Fase', orientation='h',
                        title=f"Linha do Tempo: Contrato {contrato_escolhido} ({vigencia_meses} meses totais)",
                        text='Label', color='Fase', color_discrete_map={'Tempo Decorrido': '#ff7f0e', 'Tempo Restante': '#1f77b4'}
                    )
                    fig_tempo.update_layout(xaxis_title="Dias Totais", yaxis_title="")
                    st.plotly_chart(fig_tempo, use_container_width=True)
                else:
                    st.warning("⚠️ Este contrato não possui data de vencimento nas notas ou vigência cadastrada.")
    except Exception as e:
        st.error(f"Erro ao processar o cruzamento de dados: {e}")
