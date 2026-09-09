import re
import cv2
import numpy as np
import pytesseract
import streamlit as st
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
import io
from sqlalchemy import create_engine
import plotly.express as px
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ============================================
# 1.  CONFIGURAÇÃO URL DE CONEXÃO COM POSTGRES
# ============================================

# 1. Carrega as informações escondidas no arquivo .env
load_dotenv()

# 2. Puxa a URL com a senha em segurança
DB_URL = os.getenv("DATABASE_URL")

# 3. Trava de segurança caso o arquivo .env não exista
if not DB_URL:
    raise ValueError("A variável DATABASE_URL não foi encontrada. Verifique o arquivo .env!")

engine = create_engine(DB_URL)


# ==========================================
# 2. FUNÇÕES DE SUPORTE E CONVERSÃO
# ==========================================

def convert_nota_fiscal(arquivos_bytes, tipo):
    """Lida com PDF ou Imagens e retorna uma lista de imagens (PIL)"""
    if tipo == "pdf":
        caminho_poppler = r"C:\Users\renata.machado\Release-26.07.0-0\poppler-26.07.0\Library\bin"
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
# 3. SUAS FUNÇÕES DE EXTRAÇÃO DE DADOS
# ==========================================

def numero_nfe(texto):
    padroes = [
        r'Número da Nota/Série\s*([\d\.]+)\s*/',  
        r'RPS no\.\s*([\d\.]+)',                  
        r'N[uú]mero\s*da\s*Nota\s*[:]?\s*(\d+)',  
        r'NFS-e\s*N[ºo]?\s*[:]?\s*(\d+)',         
        r'N[ºo]\s*[:]?\s*(\d+)'                   
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1).replace('.', '')
    return ""

def emissao_nota(texto):
    padroes = [
        r'Data e Hora de Emissão\s*(\d{2}/\d{2}/\d{4})', 
        r'Emitido em\s*[:]?\s*(\d{2}/\d{2}/\d{4})',       
        r'Data\s*de\s*Emissão\s*[:]?\s*(\d{2}/\d{2}/\d{4})', 
        r'Competência\s*[:]?\s*(\d{2}/\d{2}/\d{4})'       
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""

def vencimento(texto):
    padroes = [
        r'Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})', 
        r'Data de Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})' 
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
# 4. FUNÇÕES DE BANCO E INTERFACE
# ==========================================

def armazena_info(lista_dados_finais):
    """Recebe a lista validada pelo usuário e insere no PostgreSQL"""
    try:
        df_para_salvar = pd.DataFrame(lista_dados_finais)
        # O if_exists='append' insere novas notas sem apagar as antigas
        df_para_salvar.to_sql('notas_fiscais', con=engine, if_exists='append', index=False)
        
        quantidade = len(lista_dados_finais)
        st.success(f"✅ {quantidade} nota(s) armazenada(s) no banco de dados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao conectar ou salvar no banco: {e}")

def balanco_nota_fiscal():
    st.header("📈 Balanço de Notas Fiscais (Dashboard)")
    
    try:
        # Lê a tabela direto do Postgres
        df = pd.read_sql_table('notas_fiscais', con=engine)
        
        if df.empty:
            st.info("Nenhuma nota fiscal registrada no banco ainda.")
            return

        # Filtros laterais
        st.sidebar.subheader("Filtros")
        emissor_filtro = st.sidebar.multiselect("Filtrar por CNPJ do Emitente", options=df['cnpj_emitente'].unique())
        
        if emissor_filtro:
            df = df[df['cnpj_emitente'].isin(emissor_filtro)]
        
        # Cards de métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("Valor Total Bruto", f"R$ {df['valor_total'].sum():,.2f}")
        col2.metric("Total Impostos Retidos", f"R$ {df['valor_ir'].sum():,.2f}")
        col3.metric("Valor Total Líquido", f"R$ {df['valor_liquido'].sum():,.2f}")
        
        st.divider()
        
        # Gráfico e Tabela
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            df_agrupado = df.groupby('cnpj_emitente')['valor_total'].sum().reset_index()
            fig1 = px.bar(df_agrupado, x='cnpj_emitente', y='valor_total', title="Faturamento por Emitente",
                          labels={'cnpj_emitente': 'CNPJ', 'valor_total': 'Valor (R$)'})
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            st.write("### Detalhamento das Notas")
            st.dataframe(df[['numero_nfe', 'data_emissao', 'cnpj_emitente', 'valor_total', 'valor_liquido']], use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning(f"Não foi possível ler o banco de dados. Verifique se o Docker está rodando. Erro: {e}")

def processa_nota():
    st.header("Upload e Leitura de Notas Fiscais")
    
    arquivos_upload = st.file_uploader(
        "Faça o upload das notas fiscais (pdf ou imagem)", 
        type=["pdf", "png", "jpg", "jpeg"], 
        accept_multiple_files=True
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
                        if qrcode_lido:
                            st.toast(f"✅ QR Code detectado em {arquivo.name}")
                        
                        texto_ocr = extrair_texto_unico(imagens)
                        
                        v_total = valor_total(texto_ocr)
                        v_ir = valor_ir(v_total)
                        v_liq = valor_liquido(v_total, v_ir)
                        
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
                
                progresso.progress((i + 1) / total)
                
            st.session_state['dados_extraidos'] = lista_resultados
            st.success("Leitura concluída! Verifique os dados abaixo.")

    if 'dados_extraidos' in st.session_state:
        st.divider()
        st.subheader("Verifique e Salve as Informações")
        st.caption("Você pode clicar diretamente na tabela para editar qualquer valor lido incorretamente antes de salvar.")
        
        df = pd.DataFrame(st.session_state['dados_extraidos'])
        tabela_editada = st.data_editor(df, use_container_width=True, hide_index=True)
        
        if st.button("Armazenar Todas as Informações"):
            dados_atualizados = tabela_editada.to_dict('records')
            armazena_info(dados_atualizados)
            
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