"""
Pagina: Notas de Empenho -- leitura via IA/regex, conferencia e cadastro no banco.
"""
import streamlit as st
import pandas as pd
import numpy as np
import time

from nfe_app.config import engine
from nfe_app.ocr_utils import convert_nota_fiscal, extrair_dados_ocr_tabular, reconstruir_texto_corrido
from nfe_app.extract_contratos_ia import extrair_dados_empenho_via_ia
from nfe_app.extract_empenho import (
    extrair_numero_empenho, extrai_fonte_empenho, extrai_cod_unico_empenho,
    extrai_processo_sei_empenho, extrai_cnpj_empenho, extrai_numero_contrato_empenho,
    extrai_natureza_empenho, extrai_valor_empenho, extrai_assunto_empenho, extrai_ug_empenho,
)
from nfe_app.formatters import formata_valor

def gerenciar_empenhos():
    st.header("🧾 Leitura e Upload de Notas de Empenho (NE)")
    st.markdown("Faça o upload do **PDF da Nota de Empenho**.")
    
    col_upload, col_debug = st.columns([3, 1])
    with col_upload:
        arquivos_ne = st.file_uploader("Upload das Notas de Empenho em PDF", type=["pdf"], accept_multiple_files=True, key="uploader_ne")
    with col_debug:
        st.write("")
        st.write("")
        forcar_ocr = st.checkbox("🕵️ Modo Debug (Forçar OCR)", value=False, help="Desativa a IA temporariamente para ver o texto bruto OCR.")
    
    if arquivos_ne:
        if st.button("Processar Notas de Empenho"):
            lista_ne_extraidas = []
            progresso = st.progress(0)
            total = len(arquivos_ne)
            
            for i, arquivo in enumerate(arquivos_ne):
                bytes_arquivo = arquivo.read()
                
                with st.spinner(f"Processando NE {arquivo.name} ({i+1}/{total})..."):
                    usou_ia_com_sucesso = False
                    
                    if not forcar_ocr:
                        try:
                            dados_ia = extrair_dados_empenho_via_ia(bytes_arquivo, arquivo.name)
                            
                            num_ne = str(dados_ia.get("numero_empenho", ""))
                            proc_sei = str(dados_ia.get("processo_sei", ""))
                            cnpj = str(dados_ia.get("cnpj_credor", ""))
                            num_cont = str(dados_ia.get("numero_contrato", ""))
                            nat_desp = str(dados_ia.get("natureza_despesa", ""))
                            fonte = str(dados_ia.get("fonte_recurso", ""))
                            valor = float(dados_ia.get("valor_empenhado", 0.0))
                            ug = str(dados_ia.get("ug", ""))
                            assunto = str(dados_ia.get("assunto", ""))
                            
                            if num_ne and valor > 0:
                                usou_ia_com_sucesso = True
                                st.toast(f"🤖 IA extraiu dados da NE {arquivo.name} com sucesso!")
                            time.sleep(4)
                            
                        except Exception as e:
                            usou_ia_com_sucesso = False
                    else:
                        st.toast("Modo Debug Ativado: IA ignorada. Rodando OCR puro...")

                    if not usou_ia_com_sucesso:
                        imagens = convert_nota_fiscal(bytes_arquivo, "pdf")
                        if imagens:
                            df_ocr_ne = extrair_dados_ocr_tabular(imagens)
                            texto_ne = reconstruir_texto_corrido(df_ocr_ne)
                            
                            with st.expander(f"🕵️ Ver Saída Bruta do OCR ({arquivo.name})", expanded=forcar_ocr):
                                st.write("**1. Texto Corrido Montado pelo OCR:**")
                                st.info(texto_ne)
                                st.write("**2. Tabela de Leitura (DataFrame):**")
                                st.dataframe(df_ocr_ne[['text', 'block_num', 'line_num', 'conf']])
                            
                            num_ne = extrair_numero_empenho(texto_ne)
                            proc_sei = extrai_processo_sei_empenho(texto_ne)
                            cnpj = extrai_cnpj_empenho(texto_ne)
                            num_cont = extrai_numero_contrato_empenho(texto_ne)
                            nat_desp = extrai_natureza_empenho(texto_ne)
                            fonte = extrai_fonte_empenho(texto_ne)
                            valor = extrai_valor_empenho(texto_ne)
                            ug = extrai_ug_empenho(texto_ne)
                            assunto = extrai_assunto_empenho(texto_ne)
                        else:
                            st.error(f"Falha ao converter o PDF {arquivo.name}.")
                            continue
                    
                    lista_ne_extraidas.append({
                        "numero_ne": num_ne,
                        "processo_sei": proc_sei,
                        "cnpj_credor": cnpj,
                        "numero_contrato": num_cont,
                        "natureza_despesa": nat_desp,
                        "fonte_recurso": fonte,
                        "valor_empenhado": valor,
                        "ug": ug,
                        "assunto": assunto,
                        "arquivo_origem": arquivo.name
                    })
                    
                progresso.progress((i + 1) / total)
                
            st.session_state['nes_extraidas'] = lista_ne_extraidas
            st.success("Leitura das Notas de Empenho concluída!")

    if 'nes_extraidas' in st.session_state:
        st.divider()
        st.subheader("Conferência e Salvamento das NEs")
        df_edit_ne = pd.DataFrame(st.session_state['nes_extraidas'])
        
        try:
            df_contratos_sei = pd.read_sql('SELECT numero_contrato AS num_cont_db, processo_sei FROM resumo_contratos WHERE processo_sei IS NOT NULL', con=engine)
            df_contratos_sei = df_contratos_sei[df_contratos_sei['processo_sei'].str.strip() != '']
            df_contratos_sei = df_contratos_sei.drop_duplicates(subset=['processo_sei'])
            
            df_edit_ne = pd.merge(df_edit_ne, df_contratos_sei, on='processo_sei', how='left')
            
            df_edit_ne['numero_contrato'] = np.where(
                (df_edit_ne['numero_contrato'].isna()) | (df_edit_ne['numero_contrato'] == ""),
                df_edit_ne['num_cont_db'],
                df_edit_ne['numero_contrato']
            )
            df_edit_ne = df_edit_ne.drop(columns=['num_cont_db'])
            df_edit_ne['numero_contrato'] = df_edit_ne['numero_contrato'].fillna("")
        except Exception:
            pass 
            
        tabela_ne_editada = st.data_editor(
            df_edit_ne, use_container_width=True, hide_index=True,
            column_config={
                "numero_ne": st.column_config.TextColumn("Número da NE"),
                "processo_sei": st.column_config.TextColumn("Processo SEI"),
                "cnpj_credor": st.column_config.TextColumn("CNPJ Credor"),
                "numero_contrato": st.column_config.TextColumn("Contrato Vinculado"),
                "natureza_despesa": st.column_config.TextColumn("Natureza da Despesa"),
                "fonte_recurso": st.column_config.TextColumn("Fonte de Recurso"),
                "valor_empenhado": st.column_config.NumberColumn("Valor Empenhado", format="R$ %.2f"),
                "ug": st.column_config.TextColumn("UG"),
                "assunto": st.column_config.TextColumn("Assunto"),
                "arquivo_origem": st.column_config.TextColumn("Arquivo PDF")
            }
        )
        
        if st.button("Confirmar e Salvar NEs no Banco"):
            try:
                df_para_banco = tabela_ne_editada[['numero_ne', 'processo_sei', 'cnpj_credor', 'numero_contrato', 'natureza_despesa', 'fonte_recurso', 'valor_empenhado', 'ug', 'assunto']].copy()
                
                try:
                    df_existente = pd.read_sql('SELECT numero_ne FROM notas_empenho', con=engine)
                    if not df_existente.empty:
                        df_para_banco = df_para_banco[~df_para_banco['numero_ne'].isin(df_existente['numero_ne'])]
                except Exception:
                    pass 
                
                if df_para_banco.empty:
                    st.warning("⚠️ Nenhuma Nota de Empenho nova para salvar. Todas já existem no banco!")
                else:
                    df_para_banco.to_sql('notas_empenho', con=engine, if_exists='append', index=False)
                    st.success(f"✅ {len(df_para_banco)} Nota(s) de Empenho salva(s) com sucesso!")
                    st.balloons()
                
                del st.session_state['nes_extraidas']
                time.sleep(3)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar NE no banco: {e}")

    st.divider()
    st.subheader("🗄️ Notas de Empenho Registradas no Banco de Dados")
    try:
        df_banco_ne = pd.read_sql_table('notas_empenho', con=engine)
        if df_banco_ne.empty:
            st.info("Nenhuma Nota de Empenho cadastrada no banco de dados até o momento.")
        else:
            df_exib_ne = df_banco_ne.copy()
            
            try:
                df_contratos = pd.read_sql('SELECT numero_contrato AS contrato_via_sei, processo_sei FROM resumo_contratos WHERE processo_sei IS NOT NULL', con=engine)
                df_contratos = df_contratos[df_contratos['processo_sei'].str.strip() != '']
                df_contratos = df_contratos.drop_duplicates(subset=['processo_sei'])
                
                df_exib_ne = pd.merge(df_exib_ne, df_contratos, on='processo_sei', how='left')
                
                df_exib_ne['status_vinculo'] = np.where(
                    df_exib_ne['contrato_via_sei'].notna(),
                    "🔗 Vinculado por SEI",
                    "⚠️ Sem Contrato"
                )
            except Exception as e:
                df_exib_ne['status_vinculo'] = "Aguardando Contratos"

            if 'valor_empenhado' in df_exib_ne.columns:
                df_exib_ne['valor_empenhado'] = df_exib_ne['valor_empenhado'].apply(formata_valor)
            
            cols_order = ['numero_ne', 'processo_sei', 'status_vinculo', 'numero_contrato', 'cnpj_credor', 'natureza_despesa', 'fonte_recurso', 'valor_empenhado', 'ug', 'assunto']
            cols_to_show = [c for c in cols_order if c in df_exib_ne.columns]
            
            st.dataframe(
                df_exib_ne[cols_to_show], use_container_width=True, hide_index=True,
                column_config={
                    "numero_ne": st.column_config.TextColumn("Número da NE"),
                    "processo_sei": st.column_config.TextColumn("Processo SEI"),
                    "status_vinculo": st.column_config.TextColumn("Status do Vínculo"),
                    "numero_contrato": st.column_config.TextColumn("Contrato"),
                    "cnpj_credor": st.column_config.TextColumn("CNPJ Credor"),
                    "natureza_despesa": st.column_config.TextColumn("Natureza Despesa"),
                    "fonte_recurso": st.column_config.TextColumn("Fonte Recurso"),
                    "valor_empenhado": st.column_config.TextColumn("Valor Empenhado"),
                    "ug": st.column_config.TextColumn("UG"),
                    "assunto": st.column_config.TextColumn("Assunto")
                }
            )
    except Exception:
        st.info("A tabela de Notas de Empenho ainda não foi criada no banco.")
