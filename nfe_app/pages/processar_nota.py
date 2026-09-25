"""
Pagina: Processador de Nota -- upload, OCR/QR Code e extracao dos dados da nota fiscal.
"""
import streamlit as st
import pandas as pd

from nfe_app.ocr_utils import (
    convert_nota_fiscal, ler_qrcode_imagem, extrair_dados_ocr_tabular, reconstruir_texto_corrido,
)
from nfe_app.extract_nfe import (
    numero_nfe, razao_social_emitente, emissao_nota, vencimento,
    cnpj_emitente, cnpj_pagador, valor_iss, valor_total, valor_liquido,
    valor_ir, numero_contrato,
)
from nfe_app.excel_export import gerar_excel_levantamento, gerar_excel_calculo_pagto
from nfe_app.ui_helpers import armazena_info

def processa_nota():
    st.header("Upload e Leitura de Notas Fiscais")
    
    if 'chave_uploader_notas' not in st.session_state:
        st.session_state['chave_uploader_notas'] = 0

    arquivos_upload = st.file_uploader(
        "Faça o upload das notas fiscais (pdf ou imagem)", 
        type=["pdf", "png", "jpg", "jpeg"], 
        accept_multiple_files=True,
        key=f"uploader_notas_{st.session_state['chave_uploader_notas']}"
    )
    if arquivos_upload:
        if st.button("Ler Notas Fiscais"):
            lista_resultados = []
            progresso = st.progress(0)
            total = len(arquivos_upload)
            
            for i, arquivo in enumerate(arquivos_upload):
                tipo = arquivo.name.lower().split(".")[-1]
                bytes_arquivo = arquivo.read()
                
                with st.spinner(f"Processando {arquivo.name} ({i+1}/{total})..."):
                    imagens = convert_nota_fiscal(bytes_arquivo, tipo)
                    if imagens:
                        qrcode_lido = ler_qrcode_imagem(imagens[0])
                        if qrcode_lido: st.toast(f"✅ QR Code detectado em {arquivo.name}")
                        
                        df_ocr = extrair_dados_ocr_tabular(imagens)
                        texto_ocr = reconstruir_texto_corrido(df_ocr)
                        
                        with st.expander(f"🕵️ Ver DataFrame Tabular do OCR ({arquivo.name})"):
                            st.dataframe(df_ocr[['text', 'block_num', 'line_num', 'conf']])
                        
                        v_total = valor_total(df_ocr, texto_ocr)
                        v_liq = valor_liquido(df_ocr, texto_ocr)
                        v_iss = valor_iss(df_ocr, texto_ocr)
                        v_ir = valor_ir(df_ocr, texto_ocr)
                        
                        if v_liq == 0.0 and v_total > 0 and v_ir > 0:
                            v_liq = round(v_total - v_ir, 2)
                        
                        num_contr = numero_contrato(texto_ocr)
                        cnpj_emissao = cnpj_emitente(texto_ocr)
                        
                        if not num_contr or num_contr == "N/A":
                            num_contr = f"CNPJ: {cnpj_emissao}" if cnpj_emissao else "Não Identificado"
                        
                        nome_empresa = razao_social_emitente(df_ocr, texto_ocr)
                        if nome_empresa == "NÃO IDENTIFICADO": nome_empresa = arquivo.name 
                        
                        lista_resultados.append({
                            "Arquivo": nome_empresa, 
                            "numero_nfe": numero_nfe(df_ocr, texto_ocr),
                            "numero_contrato": num_contr,
                            "data_emissao": emissao_nota(texto_ocr),
                            "vencimento": vencimento(texto_ocr),
                            "cnpj_emitente": cnpj_emissao,
                            "cnpj_pagador": cnpj_pagador(texto_ocr),
                            "valor_total": v_total,
                            "valor_ir": v_ir,
                            "valor_iss": v_iss,
                            "valor_liquido": v_liq
                        })
                    else:
                        st.error(f"Falha ao converter o arquivo {arquivo.name}.")
                progresso.progress((i + 1) / total)
            st.session_state['dados_extraidos'] = lista_resultados
            st.success("Leitura concluída! Verifique os dados abaixo.")

    if 'dados_extraidos' in st.session_state:
        st.divider()
        st.subheader("Verifique e Salve as Informações")
        st.caption("Você pode clicar diretamente na tabela para editar qualquer valor lido incorretamente antes de salvar.")
        
        df = pd.DataFrame(st.session_state['dados_extraidos'])
        tabela_editada = st.data_editor(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Arquivo": st.column_config.TextColumn("Nome da Empresa"),
                "valor_total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "valor_ir": st.column_config.NumberColumn("Valor IR", format="R$ %.2f"),
                "valor_iss": st.column_config.NumberColumn("Valor ISS", format="R$ %.2f"),       
                "valor_liquido": st.column_config.NumberColumn("Valor Líquido", format="R$ %.2f")
            }
        )
        if st.button("Armazenar Todas as Informações"):
            dados_atualizados = tabela_editada.to_dict('records')
            armazena_info(dados_atualizados)
            
        st.write("---")
        st.write("Opções de Download Rápido (sem salvar no banco):")
        
        excel_data_lev = gerar_excel_levantamento(st.session_state['dados_extraidos'])
        excel_data_calc = gerar_excel_calculo_pagto(st.session_state['dados_extraidos'])
        
        col_btn_lev, col_btn_calc = st.columns(2)
        with col_btn_lev:
            st.download_button(
                label="📥 Baixar Planilha de Levantamento",
                data=excel_data_lev,
                file_name="levantamento_rapido.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        with col_btn_calc:
            st.download_button(
                label="📥 Baixar Cálculo para Pagto",
                data=excel_data_calc,
                file_name="calculo_pagamento_rapido.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
