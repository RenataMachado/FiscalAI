"""
Pagina: Processador de Nota -- upload e extracao dos dados da nota fiscal.

Fluxo de leitura de cada arquivo:
    Plano A) OCR (Tesseract) + regex.
    Plano B) Se o OCR não encontrar o número da nota ou o valor total, a IA (Claude)
             lê o PDF/imagem diretamente. Se a IA também falhar, ficam os dados do OCR.
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
from nfe_app.extract_nfe_ia import extrair_dados_nfe_via_ia
from nfe_app.formatters import converter_float, texto_limpo_ia, formata_cnpj, formata_data
from nfe_app.excel_export import gerar_excel_levantamento, gerar_excel_calculo_pagto
from nfe_app.ui_helpers import armazena_info, registrar_tokens, mostrar_consumo_tokens

# Coluna só para conferência na tela (não existe no banco, é removida antes de salvar)
COLUNA_ORIGEM = "origem_leitura"


def _ler_nota_com_ia(bytes_arquivo, nome_arquivo):
    """Lê a nota pela IA. Devolve o dicionário no formato do app, ou None se a leitura não servir."""
    dados = extrair_dados_nfe_via_ia(bytes_arquivo, nome_arquivo)
    registrar_tokens(nome_arquivo, "Nota Fiscal", dados)

    nota = {
        "Arquivo": texto_limpo_ia(dados.get("razao_social_emitente")),
        "numero_nfe": texto_limpo_ia(dados.get("numero_nfe")).replace(".", ""),
        "numero_contrato": texto_limpo_ia(dados.get("numero_contrato")),
        "data_emissao": formata_data(texto_limpo_ia(dados.get("data_emissao"))),
        "vencimento": formata_data(texto_limpo_ia(dados.get("vencimento"))),
        "cnpj_emitente": formata_cnpj(texto_limpo_ia(dados.get("cnpj_emitente"))),
        "cnpj_pagador": formata_cnpj(texto_limpo_ia(dados.get("cnpj_pagador"))),
        "valor_total": converter_float(dados.get("valor_total")),
        "valor_ir": converter_float(dados.get("valor_ir")),
        "valor_iss": converter_float(dados.get("valor_iss")),
        "valor_liquido": converter_float(dados.get("valor_liquido")),
    }

    # Sem número da nota ou sem valor, a leitura não é confiável -> usa o OCR
    if not nota["numero_nfe"] or nota["valor_total"] <= 0:
        return None
    return nota


def _ler_nota_com_ocr(bytes_arquivo, nome_arquivo, tipo):
    """Plano B: OCR + regex (o método antigo). Devolve o dicionário ou None se não conseguir ler."""
    imagens = convert_nota_fiscal(bytes_arquivo, tipo)
    if not imagens:
        return None

    if ler_qrcode_imagem(imagens[0]):
        st.toast(f"✅ QR Code detectado em {nome_arquivo}")

    df_ocr = extrair_dados_ocr_tabular(imagens)
    texto_ocr = reconstruir_texto_corrido(df_ocr)

    with st.expander(f"🕵️ Ver DataFrame Tabular do OCR ({nome_arquivo})"):
        colunas_debug = [c for c in ['text', 'block_num', 'line_num', 'conf'] if c in df_ocr.columns]
        st.dataframe(df_ocr[colunas_debug])

    return {
        "Arquivo": razao_social_emitente(df_ocr, texto_ocr),
        "numero_nfe": numero_nfe(df_ocr, texto_ocr),
        "numero_contrato": numero_contrato(texto_ocr),
        "data_emissao": emissao_nota(texto_ocr),
        "vencimento": vencimento(texto_ocr),
        "cnpj_emitente": cnpj_emitente(texto_ocr),
        "cnpj_pagador": cnpj_pagador(texto_ocr),
        "valor_total": valor_total(df_ocr, texto_ocr),
        "valor_ir": valor_ir(df_ocr, texto_ocr),
        "valor_iss": valor_iss(df_ocr, texto_ocr),
        "valor_liquido": valor_liquido(df_ocr, texto_ocr),
    }


def _ajustes_finais(nota, nome_arquivo):
    """Regras que valem para qualquer método de leitura (IA ou OCR)."""
    # Mesma regra do código original: se não achou o líquido, calcula Bruto - IR
    if nota["valor_liquido"] == 0.0 and nota["valor_total"] > 0 and nota["valor_ir"] > 0:
        nota["valor_liquido"] = round(nota["valor_total"] - nota["valor_ir"], 2)

    if not nota["numero_contrato"] or nota["numero_contrato"] == "N/A":
        cnpj = nota["cnpj_emitente"]
        nota["numero_contrato"] = f"CNPJ: {cnpj}" if cnpj else "Não Identificado"

    if not nota["Arquivo"] or nota["Arquivo"] == "NÃO IDENTIFICADO":
        nota["Arquivo"] = nome_arquivo
    return nota


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
    st.caption("🔍 O OCR lê primeiro. Se ele não encontrar o número da nota ou o valor, "
               "a 🤖 IA entra automaticamente.")

    if arquivos_upload:
        if st.button("Ler Notas Fiscais"):
            lista_resultados = []
            progresso = st.progress(0)
            total = len(arquivos_upload)
            # A IA é sempre usada como Plano B. Ela só é desligada AUTOMATICAMENTE,
            # no meio do lote, se a conta tiver problema (chave inválida / sem créditos).
            ia_disponivel = True

            for i, arquivo in enumerate(arquivos_upload):
                tipo = arquivo.name.lower().split(".")[-1]
                bytes_arquivo = arquivo.read()

                with st.spinner(f"Processando {arquivo.name} ({i+1}/{total})..."):
                    nota, origem = None, ""

                    # ===== PLANO A: OCR + regex =====
                    nota = _ler_nota_com_ocr(bytes_arquivo, arquivo.name, tipo)
                    if nota is not None:
                        origem = "🔍 OCR"

                    # Regra para considerar a leitura do OCR boa o suficiente
                    ocr_com_sucesso = (
                        nota is not None
                        and bool(nota["numero_nfe"])
                        and converter_float(nota["valor_total"]) > 0
                    )

                    # ===== PLANO B: IA (só se o OCR não achou os dados principais) =====
                    if ocr_com_sucesso:
                        st.toast(f"🔍 OCR leu {arquivo.name} com sucesso!")
                    elif ia_disponivel:
                        st.toast(f"⚠️ OCR não encontrou os dados de {arquivo.name}. Acionando Plano B (IA)...")
                        try:
                            nota_ia = _ler_nota_com_ia(bytes_arquivo, arquivo.name)
                            if nota_ia:
                                nota, origem = nota_ia, "🤖 IA"
                                st.toast(f"🤖 IA leu {arquivo.name} com sucesso!")
                            else:
                                st.warning(f"A IA também não encontrou os dados de {arquivo.name}. Mantidos os dados do OCR; confira antes de salvar.")
                        except Exception as e:
                            st.warning(f"IA (Plano B) falhou em {arquivo.name}. Mantidos os dados do OCR. Motivo: {e}")
                            # Problema na CONTA (chave inválida, sem créditos, sem chave no .env):
                            # não adianta tentar a IA nos próximos arquivos do lote.
                            if any(t in str(e) for t in ("Chave da Anthropic inválida", "sem créditos", "não inicializado")):
                                ia_disponivel = False
                                st.info("A IA foi desativada para o restante deste lote; as próximas notas usarão só o OCR.")

                    if nota is None:
                        st.error(f"Falha ao ler o arquivo {arquivo.name} (nem IA nem OCR conseguiram).")
                    else:
                        nota = _ajustes_finais(nota, arquivo.name)
                        nota[COLUNA_ORIGEM] = origem
                        lista_resultados.append(nota)

                progresso.progress((i + 1) / total)

            st.session_state['dados_extraidos'] = lista_resultados
            st.success("Leitura concluída! Verifique os dados abaixo.")

    mostrar_consumo_tokens()

    if 'dados_extraidos' in st.session_state:
        st.divider()
        st.subheader("Verifique e Salve as Informações")
        st.caption("Você pode clicar diretamente na tabela para editar qualquer valor lido incorretamente antes de salvar. "
                   "Confira com atenção, principalmente os valores: o OCR pode achar um número errado, mas que parece certo.")

        df = pd.DataFrame(st.session_state['dados_extraidos'])
        # Coloca a coluna de origem em primeiro lugar, para ficar fácil de ver
        if COLUNA_ORIGEM in df.columns:
            df = df[[COLUNA_ORIGEM] + [c for c in df.columns if c != COLUNA_ORIGEM]]

        tabela_editada = st.data_editor(
            df, use_container_width=True, hide_index=True,
            disabled=[COLUNA_ORIGEM],
            column_config={
                COLUNA_ORIGEM: st.column_config.TextColumn("Lido por"),
                "Arquivo": st.column_config.TextColumn("Nome da Empresa"),
                "valor_total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                "valor_ir": st.column_config.NumberColumn("Valor IR", format="R$ %.2f"),
                "valor_iss": st.column_config.NumberColumn("Valor ISS", format="R$ %.2f"),
                "valor_liquido": st.column_config.NumberColumn("Valor Líquido", format="R$ %.2f")
            }
        )

        # A coluna "Lido por" é só para a tela: não existe no banco nem nas planilhas
        dados_editados = tabela_editada.drop(columns=[COLUNA_ORIGEM], errors="ignore").to_dict('records')

        if st.button("Armazenar Todas as Informações"):
            armazena_info(dados_editados)

        st.write("---")
        st.write("Opções de Download Rápido (sem salvar no banco):")

        excel_data_lev = gerar_excel_levantamento(dados_editados)
        excel_data_calc = gerar_excel_calculo_pagto(dados_editados)

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
