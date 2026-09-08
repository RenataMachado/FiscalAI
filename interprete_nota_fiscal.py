import re
import cv2
import numpy as np
import pytesseract
import streamlit as st
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
import io

# ==========================================
# 1. FUNÇÕES DE SUPORTE E CONVERSÃO
# ==========================================

def convert_nota_fiscal(arquivos_bytes, tipo):
    """Lida com PDF ou Imagens e retorna uma lista de imagens (PIL)"""
    if tipo == "pdf":
        return convert_from_bytes(arquivos_bytes)
    elif tipo in ["png", "jpg", "jpeg"]:
        img = Image.open(io.BytesIO(arquivos_bytes))
        return [img]
    return []

def ler_qrcode_imagem(imagem_pill):
    """Usa o OpenCV nativo para ler QR Code"""
    # Converte a imagem para o formato do OpenCV
    imagem_np = np.array(imagem_pill)
    
    # Chama o leitor nativo do OpenCV
    detector = cv2.QRCodeDetector()
    
    # Tenta ler o QR Code
    texto, bbox, _ = detector.detectAndDecode(imagem_np)
    
    # Retorna o texto dentro de uma lista se encontrar algo
    if texto:
        return [texto]
    return []

def extrair_texto_unico(lista_imagens):
    """Roda o OCR apenas uma vez em todas as páginas para não travar o app"""
    texto_completo = ""
    for img in lista_imagens:
        texto_completo += pytesseract.image_to_string(img, lang="por") + "\n"
    return texto_completo

# ==========================================
# 2. SUAS FUNÇÕES DE EXTRAÇÃO DE DADOS
# ==========================================

def numero_nfe(texto):
    match = re.search(r'N[ºo]\s*[:]?\s*(\d+)', texto, re.IGNORECASE)
    return match.group(1) if match else ""

def emissao_nota(texto):
    match = re.search(r'Emissão\s*[:]?\s*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
    return match.group(1) if match else ""

def vencimento(texto):
    match = re.search(r'Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
    return match.group(1) if match else ""

def cnpj_emitente(texto):
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    return cnpjs[0] if len(cnpjs) > 0 else ""

def cnpj_pagador(texto):
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    return cnpjs[1] if len(cnpjs) > 1 else ""

def valor_total(texto):
    match = re.search(r'Valor Total.*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto, re.IGNORECASE)
    if match:
        valor_str = match.group(1).replace('.', '').replace(',', '.')
        return float(valor_str)
    return 0.0

def valor_ir(total):
    return round(total * 0.048, 2)

def valor_liquido(total, imposto):
    return round(total - imposto, 2)

# ==========================================
# 3. FUNÇÕES DE BANCO E INTERFACE
# ==========================================

def armazena_info(dados_finais):
    """Aqui salvaremos no banco de dados futuramente"""
    st.success(f"Nota {dados_finais['numero_nfe']} armazenada em memória com sucesso!")

def balanco_nota_fiscal():
    st.header("📈 Balanço de Notas Fiscais (Dashboard)")
    st.info("Em breve, aqui ficará o painel com os filtros e valores agregados.")

def processa_nota():
    st.header("Upload e Leitura de Notas Fiscais")
    arquivo_upload = st.file_uploader("Faça o upload da nota fiscal (pdf ou imagem)", type=["pdf", "png", "jpg", "jpeg"])
    
    if arquivo_upload is not None:
        tipo = arquivo_upload.name.lower().split(".")[-1]
        bytes_arquivo = arquivo_upload.read()
        
        if st.button("Ler Nota Fiscal"):
            with st.spinner("Processando imagem e lendo texto (OCR)..."):
                imagens = convert_nota_fiscal(bytes_arquivo, tipo)
                
                if imagens:
                    # Testando o leitor de QRCode apenas na primeira página para exemplo
                    qrcode_lido = ler_qrcode_imagem(imagens[0])
                    if qrcode_lido:
                        st.toast(f"✅ QR Code detectado: {qrcode_lido[0]}")
                    
                    texto_ocr = extrair_texto_unico(imagens)
                    
                    v_total = valor_total(texto_ocr)
                    v_ir = valor_ir(v_total)
                    v_liq = valor_liquido(v_total, v_ir)
                    
                    st.session_state['dados_extraidos'] = {
                        "numero_nfe": numero_nfe(texto_ocr),
                        "data_emissao": emissao_nota(texto_ocr),
                        "vencimento": vencimento(texto_ocr),
                        "cnpj_emitente": cnpj_emitente(texto_ocr),
                        "cnpj_pagador": cnpj_pagador(texto_ocr),
                        "valor_total": v_total,
                        "valor_ir": v_ir,
                        "valor_liquido": v_liq
                    }
                    st.success("Leitura concluída! Role para baixo para verificar.")
                else:
                    st.error("Falha ao converter o arquivo.")

    # Se a leitura já aconteceu, mostra o formulário para o usuário confirmar
    if 'dados_extraidos' in st.session_state:
        st.divider()
        st.subheader("Verifique e Salve as Informações")
        dados = st.session_state['dados_extraidos']
        
        with st.form("form_salvar_nota"):
            col1, col2 = st.columns(2)
            
            nfe = col1.text_input("Nº NFE", dados['numero_nfe'])
            emissao = col2.text_input("Emissão", dados['data_emissao'])
            emitente = col1.text_input("CNPJ Emitente", dados['cnpj_emitente'])
            pagador = col2.text_input("CNPJ Pagador", dados['cnpj_pagador'])
            venc = col1.text_input("Vencimento", dados['vencimento'])
            
            val_tot = col2.number_input("Valor Total", value=float(dados['valor_total']))
            val_ir = col1.number_input("Valor IR (4,8%)", value=float(dados['valor_ir']))
            val_liq = col2.number_input("Valor Líquido", value=float(dados['valor_liquido']))
            
            if st.form_submit_button("Armazenar Informação"):
                dados_atualizados = {
                    "numero_nfe": nfe, "data_emissao": emissao, "vencimento": venc,
                    "cnpj_emitente": emitente, "cnpj_pagador": pagador,
                    "valor_total": val_tot, "valor_ir": val_ir, "valor_liquido": val_liq
                }
                armazena_info(dados_atualizados)
                del st.session_state['dados_extraidos'] # Limpa a tela após salvar

# ==========================================
# MAIN
# ==========================================

def main():
    st.set_page_config(page_title="Leitor NFe", layout="wide")
    st.title("Sistema de Gestão de Notas Fiscais")
    
    menu = st.sidebar.radio("Navegação", ["Processar Nota", "Balanço (Dashboard)"])
    
    if menu == "Processar Nota":
        processa_nota()
    else:
        balanco_nota_fiscal()

if __name__ == "__main__":
    main()