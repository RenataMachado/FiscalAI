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
        
        caminho_poppler = r"C:\Users\renata.machado\Release-26.07.0-0\poppler-26.07.0\Library\bin"
        
        # Forçando o pdf2image a olhar para essa pasta
        return convert_from_bytes(arquivos_bytes, poppler_path=caminho_poppler)
        
    elif tipo in ["png", "jpg", "jpeg"]:
        img = Image.open(io.BytesIO(arquivos_bytes))
        return [img]
    return []

def ler_qrcode_imagem(imagem_pill):
    """Usa o OpenCV nativo para ler QR Code"""
    imagem_np = np.array(imagem_pill)
    detector = cv2.QRCodeDetector()
    texto, bbox, _ = detector.detectAndDecode(imagem_np)
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
    # Lista de padrões que podem aparecer na nota (do mais específico para o mais genérico)
    padroes = [
        r'Número da Nota/Série\s*([\d\.]+)\s*/',  # Ex: Número da Nota/Série 2.245.430/NFE
        r'RPS no\.\s*([\d\.]+)',                  # Ex: RPS no. 215.183
        r'N[uú]mero\s*da\s*Nota\s*[:]?\s*(\d+)',  # Ex: Número da Nota: 12345
        r'NFS-e\s*N[ºo]?\s*[:]?\s*(\d+)',         # Ex: NFS-e Nº 12345
        r'N[ºo]\s*[:]?\s*(\d+)'                   # Ex: Nº: 12345 (Padrão mais genérico)
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            # Retorna tirando possíveis pontos (ex: 2.245.430 vira 2245430)
            return match.group(1).replace('.', '')
            
    return ""

def emissao_nota(texto):
    padroes = [
        r'Data e Hora de Emissão\s*(\d{2}/\d{2}/\d{4})', 
        r'Emitido em\s*[:]?\s*(\d{2}/\d{2}/\d{4})',       # Ex: Emitido em: 20/07/2026
        r'Data\s*de\s*Emissão\s*[:]?\s*(\d{2}/\d{2}/\d{4})', # Padrão mais comum
        r'Competência\s*[:]?\s*(\d{2}/\d{2}/\d{4})'       # Algumas notas usam competência
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1)
            
    return ""

def vencimento(texto):
    padroes = [
        r'Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})', # Ex: Vencimento: 20/07/2026
        r'Data de Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})' # Padrão mais comum
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1)
            
    return ""

def cnpj_emitente(texto):
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    return cnpjs[0] if len(cnpjs) > 0 else ""

def cnpj_pagador(texto):
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto)
    return cnpjs[1] if len(cnpjs) > 1 else ""

def valor_total(texto):
    padroes = [
        r'Valor Total.*?(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Valor do Servi[çc]o.*?(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Total.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
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

def armazena_info(lista_dados_finais):
    """Agora recebe uma lista com os dados de todas as notas processadas"""
    quantidade = len(lista_dados_finais)
    st.success(f"✅ {quantidade} nota(s) armazenada(s) em memória com sucesso!")

def balanco_nota_fiscal():
    st.header("📈 Balanço de Notas Fiscais (Dashboard)")
    st.info("Em breve, aqui ficará o painel com os filtros e valores agregados.")

def processa_nota():
    st.header("Upload e Leitura de Notas Fiscais")
    
    # ADIÇÃO: accept_multiple_files=True permite selecionar N arquivos
    arquivos_upload = st.file_uploader(
        "Faça o upload das notas fiscais (pdf ou imagem)", 
        type=["pdf", "png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    # Verificamos se a lista de arquivos não está vazia
    if arquivos_upload:
        
        if st.button("Ler Notas Fiscais"):
            # Lista vazia para guardar os resultados de todos os arquivos
            lista_resultados = []
            
            # Barra de progresso para acompanhar a leitura
            progresso = st.progress(0)
            total = len(arquivos_upload)
            
            # LOOP: Passando por cada arquivo enviado
            for i, arquivo in enumerate(arquivos_upload):
                tipo = arquivo.name.lower().split(".")[-1]
                bytes_arquivo = arquivo.read()
                
                with st.spinner(f"Processando {arquivo.name} ({i+1}/{total})..."):
                    imagens = convert_nota_fiscal(bytes_arquivo, tipo)
                    
                    if imagens:
                        qrcode_lido = ler_qrcode_imagem(imagens[0])
                        if qrcode_lido:
                            st.toast(f"✅ QR Code detectado em {arquivo.name}")
                        
                        texto_ocr = extrair_texto_unico(imagens)
                        
                        v_total = valor_total(texto_ocr)
                        v_ir = valor_ir(v_total)
                        v_liq = valor_liquido(v_total, v_ir)
                        
                        # Adicionando os dados desta nota à nossa lista geral
                        lista_resultados.append({
                            "Arquivo": arquivo.name,
                            "numero_nfe": numero_nfe(texto_ocr),
                            "data_emissao": emissao_nota(texto_ocr),
                            "vencimento": vencimento(texto_ocr),
                            "cnpj_emitente": cnpj_emitente(texto_ocr),
                            "cnpj_pagador": cnpj_pagador(texto_ocr),
                            "valor_total": v_total,
                            "valor_ir": v_ir,
                            "valor_liquido": v_liq
                        })
                    else:
                        st.error(f"Falha ao converter o arquivo {arquivo.name}.")
                
                # Atualizando barra de progresso
                progresso.progress((i + 1) / total)
                
            # Salvando a lista completa na memória temporária do Streamlit
            st.session_state['dados_extraidos'] = lista_resultados
            st.success("Leitura concluída! Verifique os dados abaixo.")

    # Se a leitura já aconteceu, mostramos a tabela em vez do form antigo
    if 'dados_extraidos' in st.session_state:
        st.divider()
        st.subheader("Verifique e Salve as Informações")
        st.caption("Você pode clicar diretamente na tabela para editar qualquer valor lido incorretamente antes de salvar.")
        
        # Transforma a lista de dados em uma tabela editável
        df = pd.DataFrame(st.session_state['dados_extraidos'])
        tabela_editada = st.data_editor(df, use_container_width=True, hide_index=True)
        
        if st.button("Armazenar Todas as Informações"):
            # Converte a tabela de volta para dicionário e envia para a sua função
            dados_atualizados = tabela_editada.to_dict('records')
            armazena_info(dados_atualizados)
            
            # Limpa os dados da tela
            del st.session_state['dados_extraidos']
            st.rerun()

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