"""
Pagina: Termos Aditivos -- leitura, extracao via IA e vinculacao aos contratos.
"""
import streamlit as st
import pandas as pd

from nfe_app.config import engine
from nfe_app.ocr_utils import convert_nota_fiscal, extrair_dados_ocr_tabular, reconstruir_texto_corrido
from nfe_app.extract_contratos_ia import (
    extrair_dados_via_ia, extrair_numero_contrato_pdf,
    extrair_numero_contrato_spaguas, extrair_valor_contrato_pdf,
    extrair_vigencia_contrato_pdf, converter_vigencia_para_inteiro,
)
from nfe_app.ui_helpers import registrar_tokens, mostrar_consumo_tokens
from nfe_app.formatters import formata_valor, converter_float, converter_int, texto_limpo_ia

def gerenciar_aditivos():
    st.header("➕ Leitura e Upload de Termos Aditivos (PDF)")
    st.markdown("Faça o upload do **PDF do Termo Aditivo**.")
    arquivos_aditivo = st.file_uploader("Upload dos Aditivos em PDF", type=["pdf"], accept_multiple_files=True, key="uploader_aditivos")
    st.caption("🔍 O OCR lê primeiro. Se ele não encontrar o número do contrato, a 🤖 IA entra automaticamente.")
    
    if arquivos_aditivo:
        if st.button("Processar Termos Aditivos"):
            lista_aditivos_extraidos = []
            progresso = st.progress(0)
            total = len(arquivos_aditivo)
            
            for i, arquivo in enumerate(arquivos_aditivo):
                bytes_arquivo = arquivo.read()
                
                with st.spinner(f"Processando aditivo {arquivo.name} ({i+1}/{total})..."):
                    num_cont = num_cont_spaguas = ""
                    val_adic, meses_extra = 0.0, 0
                    origem = ""

                    # ===== PLANO A: OCR + regex =====
                    imagens = convert_nota_fiscal(bytes_arquivo, "pdf")
                    if imagens:
                        df_ocr_aditivo = extrair_dados_ocr_tabular(imagens)
                        texto_aditivo = reconstruir_texto_corrido(df_ocr_aditivo)

                        num_cont = extrair_numero_contrato_pdf(texto_aditivo, df_ocr_aditivo)
                        num_cont_spaguas = extrair_numero_contrato_spaguas(texto_aditivo, df_ocr_aditivo)
                        val_adic = extrair_valor_contrato_pdf(texto_aditivo, df_ocr_aditivo)
                        texto_vig = extrair_vigencia_contrato_pdf(texto_aditivo, df_ocr_aditivo)
                        meses_extra = converter_vigencia_para_inteiro(texto_vig)
                        origem = "🔍 OCR"

                    # Regra para considerar a leitura do OCR boa o suficiente
                    ocr_com_sucesso = bool(num_cont or num_cont_spaguas)

                    # ===== PLANO B: IA (só se o OCR não achou os dados principais) =====
                    if ocr_com_sucesso:
                        st.toast(f"🔍 OCR leu {arquivo.name} com sucesso!")
                    else:
                        st.toast(f"⚠️ OCR não encontrou os dados de {arquivo.name}. Acionando Plano B (IA)...")
                        try:
                            dados_ia = extrair_dados_via_ia(bytes_arquivo, arquivo.name, tipo_doc="aditivo")
                            registrar_tokens(arquivo.name, "Aditivo", dados_ia)

                            ia_num_cont = texto_limpo_ia(dados_ia.get("numero_contrato"))
                            ia_num_spaguas = texto_limpo_ia(dados_ia.get("numero_contrato_spaguas"))

                            if ia_num_cont or ia_num_spaguas:
                                num_cont, num_cont_spaguas = ia_num_cont, ia_num_spaguas
                                val_adic = converter_float(dados_ia.get("valor_aditivo"))
                                meses_extra = converter_int(dados_ia.get("vigencia_aditivo"))
                                origem = "🤖 IA"
                                st.toast(f"🤖 IA extraiu dados de {arquivo.name} com sucesso!")
                            else:
                                st.warning(f"A IA também não encontrou os dados de {arquivo.name}. Mantidos os dados do OCR; confira antes de salvar.")
                        except Exception as e:
                            st.warning(f"IA (Plano B) falhou em {arquivo.name}. Mantidos os dados do OCR. Motivo: {e}")

                    if not origem:
                        st.error(f"Falha ao ler o PDF {arquivo.name} (nem OCR nem IA conseguiram).")
                        continue
                            
                    if not num_cont or num_cont.upper() in ["NONE", "NULL", ""]:
                        num_cont = arquivo.name.replace('.pdf', '').replace('.PDF', '') if not num_cont_spaguas else ""
                    
                    lista_aditivos_extraidos.append({
                        "numero_contrato": num_cont,
                        "numero_contrato_spaguas": num_cont_spaguas,
                        "valor_aditivo": val_adic,
                        "vigencia_aditivo": meses_extra,
                        "arquivo_origem": arquivo.name,
                        "origem_leitura": origem
                    })
                    
                progresso.progress((i + 1) / total)
                
            st.session_state['aditivos_extraidos'] = lista_aditivos_extraidos
            st.success("Leitura dos aditivos concluída! Confira abaixo.")

    mostrar_consumo_tokens()

    if 'aditivos_extraidos' in st.session_state:
        st.divider()
        st.subheader("Conferência e Salvamento dos Aditivos")
        df_edit_adic = pd.DataFrame(st.session_state['aditivos_extraidos'])
        tabela_aditivos_editada = st.data_editor(
            df_edit_adic, use_container_width=True, hide_index=True,
            column_config={
                "numero_contrato": st.column_config.TextColumn("Nº Contrato Vinculado (PRODESP/Geral)"),
                "numero_contrato_spaguas": st.column_config.TextColumn("Nº Contrato Vinculado (SP Águas)"),
                "valor_aditivo": st.column_config.NumberColumn("Valor Aditivado", format="R$ %.2f"),
                "vigencia_aditivo": st.column_config.NumberColumn("Meses Extras de Vigência", format="%d"),
                "arquivo_origem": st.column_config.TextColumn("Arquivo PDF"),
                "origem_leitura": st.column_config.TextColumn("Lido por", disabled=True)
            }
        )
        if st.button("Confirmar e Salvar Aditivos no Banco"):
            try:
                df_para_banco = tabela_aditivos_editada[['numero_contrato', 'numero_contrato_spaguas', 'valor_aditivo', 'vigencia_aditivo']].copy()
                df_para_banco.to_sql('termos_aditivos', con=engine, if_exists='append', index=False)
                st.success("✅ Termos aditivos salvos e somados com sucesso!")
                st.balloons()
                del st.session_state['aditivos_extraidos']
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar aditivo no banco: {e}")

    st.divider()
    st.subheader("🗄️ Aditivos Registrados no Banco de Dados")
    try:
        df_banco_adic = pd.read_sql_table('termos_aditivos', con=engine)
        if df_banco_adic.empty:
            st.info("Nenhum termo aditivo cadastrado.")
        else:
            df_exib = df_banco_adic.copy()
            df_exib['valor_aditivo'] = df_exib['valor_aditivo'].apply(formata_valor)
            st.dataframe(
                df_exib, use_container_width=True, hide_index=True,
                column_config={
                    "numero_contrato": st.column_config.TextColumn("Nº Contrato Vinculado (PRODESP/Geral)"),
                    "numero_contrato_spaguas": st.column_config.TextColumn("Nº Contrato Vinculado (SP Águas)"),
                }
            )
    except Exception:
        st.info("A tabela de aditivos ainda não foi criada no banco.")
