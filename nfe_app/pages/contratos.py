"""
Pagina: Resumos Contratuais -- leitura, extracao via IA e cadastro de contratos.
"""
import streamlit as st
import pandas as pd
import time

from nfe_app.config import engine
from nfe_app.ocr_utils import convert_nota_fiscal, extrair_dados_ocr_tabular, reconstruir_texto_corrido
from nfe_app.extract_contratos_ia import (
    extrair_dados_via_ia_gemini, extrai_processo_sei, extrair_numero_contrato_pdf,
    extrair_numero_contrato_spaguas, extrair_valor_contrato_pdf,
    extrair_vigencia_contrato_pdf, converter_vigencia_para_inteiro,
)
from nfe_app.formatters import formata_valor

def gerenciar_contratos():
    st.header("📑 Leitura e Upload de Contratos")
    st.markdown("Faça o upload do **PDF do Contrato**. Para extrair o número do contrato, processo SEI, valor total e vigência.")
    arquivos_contrato = st.file_uploader("Upload dos Resumos em PDF", type=["pdf"], accept_multiple_files=True, key="uploader_contratos")
    
    if arquivos_contrato:
        if st.button("Processar Contratos PDF"):
            lista_contratos_extraidos = []
            progresso = st.progress(0)
            total = len(arquivos_contrato)
            
            for i, arquivo in enumerate(arquivos_contrato):
                bytes_arquivo = arquivo.read()
                
                with st.spinner(f"Processando contrato {arquivo.name} ({i+1}/{total})..."):
                    usou_ia_com_sucesso = False
                    
                    try:
                        dados_ia = extrair_dados_via_ia_gemini(bytes_arquivo, arquivo.name, tipo_doc="contrato")
                        
                        num_cont = str(dados_ia.get("numero_contrato", ""))
                        num_cont_spaguas = str(dados_ia.get("numero_contrato_spaguas", ""))
                        
                        num_sei = str(dados_ia.get("processo_sei") or "")
                        if num_sei.upper() == "NONE":
                            num_sei = ""
                            
                        val_cont = float(dados_ia.get("valor_contrato", 0.0))
                        tempo_vig_inteiro = int(dados_ia.get("vigencia_meses", 0))
                        
                        if (num_cont or num_cont_spaguas) and val_cont > 0:
                            usou_ia_com_sucesso = True
                            st.toast(f"🤖 IA extraiu dados de {arquivo.name} com sucesso!")
                            
                        time.sleep(4) 
                        
                    except Exception as e:
                        # --- EXIBE O ERRO DETALHADO DA IA NA TELA ---
                        st.error(f"Erro detalhado da IA no arquivo {arquivo.name}: {str(e)}")
                        st.toast(f"⚠️ IA falhou para {arquivo.name}. Acionando Plano B (OCR)...")
                        usou_ia_com_sucesso = False

                    if not usou_ia_com_sucesso:
                        imagens = convert_nota_fiscal(bytes_arquivo, "pdf")
                        if imagens:
                            df_ocr_contrato = extrair_dados_ocr_tabular(imagens)
                            texto_contrato = reconstruir_texto_corrido(df_ocr_contrato)
                            
                            num_cont = extrair_numero_contrato_pdf(texto_contrato, df_ocr_contrato)
                            num_cont_spaguas = extrair_numero_contrato_spaguas(texto_contrato, df_ocr_contrato)
                            num_sei = extrai_processo_sei(texto_contrato, df_ocr_contrato)
                            
                            val_cont = extrair_valor_contrato_pdf(texto_contrato, df_ocr_contrato)
                            texto_vig = extrair_vigencia_contrato_pdf(texto_contrato, df_ocr_contrato)
                            tempo_vig_inteiro = converter_vigencia_para_inteiro(texto_vig)
                        else:
                            st.error(f"Falha crítica: Não foi possível ler o arquivo {arquivo.name} em nenhum método.")
                            continue

                    if not num_cont or num_cont.upper() in ["NONE", "NULL", ""]:
                        num_cont = arquivo.name.replace('.pdf', '').replace('.PDF', '') if not num_cont_spaguas else ""
                    
                    lista_contratos_extraidos.append({
                        "numero_contrato": num_cont,
                        "numero_contrato_spaguas": num_cont_spaguas,
                        "processo_sei": num_sei,
                        "valor_contrato": val_cont,
                        "vigencia_contrato": tempo_vig_inteiro,
                        "arquivo_origem": arquivo.name
                    })
                    
                progresso.progress((i + 1) / total)
                
            st.session_state['contratos_extraidos'] = lista_contratos_extraidos
            st.success("Leitura dos contratos concluída! Confira abaixo.")

    if 'contratos_extraidos' in st.session_state:
        st.divider()
        st.subheader("Conferência e Salvamento dos Contratos")
        df_edit_cont = pd.DataFrame(st.session_state['contratos_extraidos'])
        tabela_contratos_editada = st.data_editor(
            df_edit_cont, use_container_width=True, hide_index=True,
            column_config={
                "numero_contrato": st.column_config.TextColumn("Nº Contrato (PRODESP/Geral)"),
                "numero_contrato_spaguas": st.column_config.TextColumn("Nº Contrato (SP Águas)"),
                "processo_sei": st.column_config.TextColumn("Processo SEI"), 
                "valor_contrato": st.column_config.NumberColumn("Valor Total do Contrato", format="R$ %.2f"),
                "vigencia_contrato": st.column_config.NumberColumn("Tempo de Vigência (Meses)", format="%d"),
                "arquivo_origem": st.column_config.TextColumn("Arquivo PDF")
            }
        )
        
        if st.button("Confirmar e Salvar Contratos no Banco"):
            try:
                df_para_banco = tabela_contratos_editada[['numero_contrato', 'numero_contrato_spaguas', 'processo_sei', 'valor_contrato', 'vigencia_contrato']].copy()
                    
                # --- INÍCIO DA TRAVA ANTI-DUPLICATAS ---
                try:
                    df_existente = pd.read_sql('SELECT numero_contrato FROM resumo_contratos', con=engine)
                    
                    if not df_existente.empty:
                        df_para_banco = df_para_banco[~df_para_banco['numero_contrato'].isin(df_existente['numero_contrato'])]
                except Exception:
                    pass 
                # --- FIM DA TRAVA ---

                if df_para_banco.empty:
                    st.warning("⚠️ Nenhum contrato novo para salvar. O(s) contrato(s) já existem no banco de dados!")
                else:
                    df_para_banco.to_sql('resumo_contratos', con=engine, if_exists='append', index=False)
                    st.success(f"✅ {len(df_para_banco)} Contrato(s) salvo(s) com sucesso!")
                    st.balloons()
                    
                if 'contratos_extraidos' in st.session_state:
                    del st.session_state['contratos_extraidos']
                st.rerun()
                    
            except Exception as e:
                st.error(f"Erro ao salvar no banco: {e}")

    st.divider()
    st.subheader("🗄️ Contratos Registrados no Banco de Dados")
    try:
        df_banco_contratos = pd.read_sql_table('resumo_contratos', con=engine)
        if df_banco_contratos.empty:
            st.info("Nenhum contrato cadastrado no banco de dados até o momento.")
        else:
            df_banco_exibicao = df_banco_contratos.copy()
            if 'valor_contrato' in df_banco_exibicao.columns:
                df_banco_exibicao['valor_contrato'] = df_banco_exibicao['valor_contrato'].apply(formata_valor)
            
            st.dataframe(
                df_banco_exibicao, use_container_width=True, hide_index=True,
                column_config={
                    "numero_contrato": st.column_config.TextColumn("Nº Contrato (PRODESP/Geral)"),
                    "numero_contrato_spaguas": st.column_config.TextColumn("Nº Contrato (SP Águas)"),
                    "processo_sei": st.column_config.TextColumn("Processo SEI"),
                    "valor_contrato": st.column_config.TextColumn("Valor Total"),
                    "vigencia_contrato": st.column_config.NumberColumn("Vigência (Meses)", format="%d"),
                    "arquivo_origem": st.column_config.TextColumn("Arquivo de Origem")
                }
            )
    except Exception:
        st.info("A tabela de contratos ainda não foi criada no banco (ou faltam colunas na tabela antiga).")