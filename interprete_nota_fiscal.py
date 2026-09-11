import re
import cv2
import numpy as np
import pytesseract
from pytesseract import Output
import streamlit as st
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
import io
from sqlalchemy import create_engine
import plotly.express as px
import os
from dotenv import load_dotenv

# ============================================
# 1. CONFIGURAÇÃO URL DE CONEXÃO COM POSTGRES
# ============================================

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if not DB_URL:
    raise ValueError("A variável DATABASE_URL não foi encontrada. Verifique o arquivo .env!")

engine = create_engine(DB_URL)


# ==========================================
# 2. FUNÇÕES DE SUPORTE, CONVERSÃO E OCR TABULAR
# ==========================================

def convert_nota_fiscal(arquivos_bytes, tipo):
    """Lida com PDF ou Imagens e retorna uma lista de imagens (PIL)"""
    if tipo == "pdf":
        caminho_poppler = os.getenv("POPPLER_PATH") 
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

def extrair_dados_ocr_tabular(lista_imagens):
    """Roda o Tesseract em formato TSV/Data (image_to_data), limpa ruídos e retorna um DataFrame estruturado com NumPy/Pandas"""
    df_completo = pd.DataFrame()
    
    for img in lista_imagens:
        df_pagina = pytesseract.image_to_data(img, lang="por", output_type=Output.DATAFRAME)
        df_completo = pd.concat([df_completo, df_pagina], ignore_index=True)
    
    # Limpeza rigorosa utilizando Pandas e NumPy para descartar linhas vazias e baixa confiança
    df_completo = df_completo.dropna(subset=['text'])
    df_completo = df_completo[df_completo['text'].str.strip() != '']
    df_completo = df_completo[df_completo['conf'] > 30] # Descarta ruídos abaixo de 30% de confiança
    
    return df_completo

def reconstruir_texto_corrido(df_ocr):
    """Gera o texto completo unificado a partir do DataFrame tabulado para buscas globais de suporte"""
    return " ".join(df_ocr['text'].astype(str))


# ==========================================
# 3. FUNÇÕES DE EXTRAÇÃO BASEADAS EM TABELA/LINHAS
# ==========================================

def numero_nfe(df_ocr, texto_geral):
    # Procura primariamente via estrutura tabular nas linhas que contêm NFS-e
    filtro = df_ocr['text'].str.contains(r'NFS-E|NOTA', case=False, regex=True)
    for _, termo in df_ocr[filtro].iterrows():
        bloco, linha = termo['block_num'], termo['line_num']
        palavras_linha = df_ocr[(df_ocr['block_num'] == bloco) & (df_ocr['line_num'] == linha)]
        texto_linha = " ".join(palavras_linha['text'].astype(str))
        
        match = re.search(r'N[uú]mero\s+da\s+NFS-e.*?(\d{1,15})\b', texto_linha, re.IGNORECASE)
        if match:
            return match.group(1)

    # Fallback por regex no texto geral limpo
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    match_prox = re.search(r'NFS-e.*?(\b\d{4,15}\b)', texto_limpo, re.IGNORECASE)
    if match_prox:
        return match_prox.group(1)
        
    return ""

def emissao_nota(texto_geral):
    padroes = [
        r'Data e Hora da emiss[ãa]o da NFS-e\s*(\d{2}/\d{2}/\d{4})', 
        r'Data e Hora de Emissão\s*(\d{2}/\d{2}/\d{4})', 
        r'Emitido em\s*[:]?\s*(\d{2}/\d{2}/\d{4})',       
        r'Data\s*de\s*Emissão\s*[:]?\s*(\d{2}/\d{2}/\d{4})', 
        r'Competência\s*[:]?\s*(\d{2}/\d{2}/\d{4})'       
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""

def vencimento(texto_geral):
    padroes = [
        r'Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})', 
        r'Data de Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})' 
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""

def cnpj_emitente(texto_geral):
    match = re.search(r'(?:EMITENTE|PRESTADOR|FORNECEDOR).*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto_geral, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto_geral)
    return cnpjs[0] if len(cnpjs) > 0 else ""

def cnpj_pagador(texto_geral):
    padroes = [
        r'TOMADOR\s*/\s*ADQUIRENTE.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'TOMADOR\s+DO\s+SERVI[ÇC]O.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'ADQUIRENTE.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'DESTINAT[ÁA]RIO.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'PAGADOR.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
            
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto_geral)
    return cnpjs[1] if len(cnpjs) > 1 else ""



def valor_total(df_ocr, texto_geral):
    """Extrai o valor total real ignorando impostos e retenções"""
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    padroes_fortes = [
        # Novo padrão para pegar "Resultado da Prestação do Serviço" (com R$ opcional)
        r'Resultado\s+da\s+Presta[çc][ãa]o\s+do\s+Servi[çc]o.*?(?:R\$)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        
        # Pega o formato da imagem image_cc897f.png (Caixa alta com barra)
        r'VALOR\s+DA\s+OPERA[ÇC][ÃA]O\s*(?:/|-)?\s*SERVI[ÇC]O.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        
        # Pega o formato direto da imagem edited-image.png
        r'Valor\s+do\s+Servi[çc]o.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        
        # Padrões alternativos
        r'VALOR\s+TOTAL\s+DA\s+NFS-e.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'BC\s+ISSQN.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    
    for padrao in padroes_fortes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            valor_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                val = float(valor_str)
                # Mantive sua regra original de ser maior que 2000
                if val >= 6000.0:  
                    return val
            except ValueError:
                continue

    # Fallback: pega o maior valor geral encontrado com "R$" antes
    valores_gerais = re.findall(r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto_limpo, re.IGNORECASE)
    if valores_gerais:
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores_gerais if v]
        if valores_float:
            return float(np.max(valores_float))
            
    return 0.0

def valor_liquido(df_ocr, texto_geral):
    """Busca diretamente o Valor Líquido impresso na nota fiscal via OCR"""
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    padroes = [
        r'VALOR\s+L[ÍI]QUIDO\s+DA\s+NFS-e.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO.*?R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            valor_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(valor_str)
            except ValueError:
                continue
                
    return 0.0

def valor_ir(df_ocr, texto_geral):
    """Busca o valor retido de IRRF, IRPJ ou Retenções Federais impresso na nota fiscal"""
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    # Padrões para buscar o imposto (com ou sem o 'R$')
    padroes_ir = [
        # Busca direta por IRRF ou IRPJ (limitando a distância para não pegar outro valor por engano)
        r'IRRF.{0,30}?(?:R\$)?\s*(\d+(?:\.\d{3})*,\d{2})',
        r'IRPJ.{0,30}?(?:R\$)?\s*(\d+(?:\.\d{3})*,\d{2})',
        
        # Padrões baseados nas imagens que você enviou
        r'Reten[çc][õo]es\s+Federais.{0,30}?(?:R\$)?\s*(\d+(?:\.\d{3})*,\d{2})',
        r'Total\s+das\s+Reten[çc][õo]es.{0,30}?(?:R\$)?\s*(\d+(?:\.\d{3})*,\d{2})',
        
        # Padrão genérico de Imposto de Renda
        r'Imposto\s+de\s+Renda.{0,30}?(?:R\$)?\s*(\d+(?:\.\d{3})*,\d{2})'
    ]
    
    for padrao in padroes_ir:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            valor_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                return float(valor_str)
            except ValueError:
                continue
                
    return 0.0
    
def numero_contrato(texto_geral):
    padroes = [
        r'CONTRATO\s+([A-Z0-9\-\.]+)',                  
        r'Número do Contrato\s*[:]?\s*([A-Z0-9\-\.]+)', 
        r'Contrato\s*[:]?\s*([A-Z0-9\-\.]+)',            
        r'No\. do Contrato\s*[:]?\s*([A-Z0-9\-\.]+)'      
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


# ==========================================
# 4. FUNÇÕES DE FORMATAÇÃO
# ==========================================

def formata_valor(valor):
    try:
        valor_float = float(valor)
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return valor

def formata_cnpj(cnpj):
    cnpj = re.sub(r'\D', '', str(cnpj))
    if len(cnpj) == 14:
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj

def formata_data(data_str):
    padrao_iso = r'(\d{4})-(\d{2})-(\d{2})'
    match_iso = re.search(padrao_iso, str(data_str))
    if match_iso:
        ano, mes, dia = match_iso.groups()
        return f"{dia}/{mes}/{ano}"
        
    padrao_br = r'(\d{2})/(\d{2})/(\d{4})'
    match_br = re.search(padrao_br, str(data_str))
    if match_br:
        dia, mes, ano = match_br.groups()
        return f"{dia}/{mes}/{ano}"
    return data_str


# ==========================================
# 5. BANCO DE DADOS E INTERFACE
# ==========================================

def armazena_info(lista_dados_finais):
    try:
        df_para_salvar = pd.DataFrame(lista_dados_finais)
        
        for col in ['data_emissao', 'vencimento']:
            if col in df_para_salvar.columns:
                df_para_salvar[col] = pd.to_datetime(df_para_salvar[col], format='%d/%m/%Y', errors='coerce').dt.strftime('%Y-%m-%d')
                
        for col in ['cnpj_emitente', 'cnpj_pagador']:
            if col in df_para_salvar.columns:
                df_para_salvar[col] = df_para_salvar[col].astype(str).str.replace(r'\D', '', regex=True)

        try:
            df_existente = pd.read_sql('SELECT numero_nfe, cnpj_emitente FROM notas_fiscais', con=engine)
            if not df_existente.empty:
                df_existente['chave'] = df_existente['numero_nfe'].astype(str) + df_existente['cnpj_emitente'].astype(str)
                df_para_salvar['chave'] = df_para_salvar['numero_nfe'].astype(str) + df_para_salvar['cnpj_emitente'].astype(str)
                df_para_salvar = df_para_salvar[~df_para_salvar['chave'].isin(df_existente['chave'])]
                df_para_salvar = df_para_salvar.drop(columns=['chave'])
        except Exception:
            pass
            
        if df_para_salvar.empty:
            st.warning("⚠️ Atenção: Todas estas notas já estavam cadastradas no banco de dados!")
            return

        df_para_salvar.to_sql('notas_fiscais', con=engine, if_exists='append', index=False)
        st.success(f"✅ {len(df_para_salvar)} nota(s) nova(s) armazenada(s) no banco de dados com sucesso!")
    except Exception as e:
        st.error(f"Erro ao conectar ou salvar no banco: {e}")

def balanco_nota_fiscal():
    st.header("📈 Balanço de Notas Fiscais (Dashboard)")
    
    try:
        df = pd.read_sql_table('notas_fiscais', con=engine)
       
        if 'numero_contrato' not in df.columns:
            df['numero_contrato'] = "N/A"
            
        if df.empty:
            st.info("Nenhuma nota fiscal registrada no banco ainda.")
            return

        st.sidebar.subheader("Filtros")
        emissor_filtro = st.sidebar.multiselect("Filtrar por CNPJ do Emitente", options=df['cnpj_emitente'].unique())
        
        if emissor_filtro:
            df = df[df['cnpj_emitente'].isin(emissor_filtro)]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Valor Total Bruto", formata_valor(df['valor_total'].sum()))
        col2.metric("Total Impostos Retidos", formata_valor(df['valor_ir'].sum()))
        col3.metric("Valor Total Líquido", formata_valor(df['valor_liquido'].sum()))
        
        st.divider()
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            df_agrupado = df.groupby('cnpj_emitente')['valor_total'].sum().reset_index()
            df_agrupado['cnpj_emitente'] = df_agrupado['cnpj_emitente'].apply(formata_cnpj)
            fig1 = px.bar(df_agrupado, x='cnpj_emitente', y='valor_total', title="Faturamento por Emitente",
                          labels={'cnpj_emitente': 'CNPJ', 'valor_total': 'Valor (R$)'})
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            st.write("### Detalhamento das Notas")
            df['cnpj_emitente'] = df['cnpj_emitente'].apply(formata_cnpj)
            df['data_emissao'] = df['data_emissao'].apply(formata_data)
            df['vencimento'] = df['vencimento'].apply(formata_data)
            df['numero_contrato'] = df['numero_contrato'].apply(lambda x: x if x else "N/A")
            st.dataframe(df[['numero_nfe', 'data_emissao', 'cnpj_emitente', 'valor_total', 'valor_liquido']], use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning(f"Não foi possível ler o banco de dados. Verifique se o banco está rodando. Erro: {e}")

def processa_nota():
    st.header("Upload e Leitura de Notas Fiscais (TSV/Pandas)")
    
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
                        
                        df_ocr = extrair_dados_ocr_tabular(imagens)
                        texto_ocr = reconstruir_texto_corrido(df_ocr)
                        
                        with st.expander(f"🕵️ Ver DataFrame Tabular do OCR ({arquivo.name})"):
                            st.dataframe(df_ocr[['text', 'block_num', 'line_num', 'conf']])
                        
                        v_total = valor_total(df_ocr, texto_ocr)
                        v_liq = valor_liquido(df_ocr, texto_ocr)
                        
                        # Tratamento caso o valor líquido venha zerado do OCR para calcular pela regra de 4.8% ou por diferença
                        v_total = valor_total(df_ocr, texto_ocr)
                        v_liq = valor_liquido(df_ocr, texto_ocr)
                        
                        # 1. NOVA CHAMADA: Passando os dois parâmetros obrigatórios!
                        v_ir = valor_ir(df_ocr, texto_ocr)
                        
                        # 2. Tratamento do líquido: Se não achar o valor líquido escrito na nota, 
                        # calcula a diferença (Total - Retenções)
                        if v_liq == 0.0 and v_total > 0 and v_ir > 0:
                            v_liq = round(v_total - v_ir, 2)
                        
                        num_contr = numero_contrato(texto_ocr)
                        cnpj_emissao = cnpj_emitente(texto_ocr)
                        
                        if not num_contr or num_contr == "N/A":
                            num_contr = f"CNPJ: {cnpj_emissao}" if cnpj_emissao else "Não Identificado"
                        
                        lista_resultados.append({
                            "Arquivo": arquivo.name,
                            "numero_nfe": numero_nfe(df_ocr, texto_ocr),
                            "numero_contrato": num_contr,
                            "data_emissao": emissao_nota(texto_ocr),
                            "vencimento": vencimento(texto_ocr),
                            "cnpj_emitente": cnpj_emissao,
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

        tabela_editada = st.data_editor(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "valor_total": st.column_config.NumberColumn(format="R$ %.2f"),
                "valor_ir": st.column_config.NumberColumn(format="R$ %.2f"),
                "valor_liquido": st.column_config.NumberColumn(format="R$ %.2f")
            }
        )
        
        if st.button("Armazenar Todas as Informações"):
            dados_atualizados = tabela_editada.to_dict('records')
            armazena_info(dados_atualizados)
            
            del st.session_state['dados_extraidos']
            st.rerun()

# ==========================================
# MAIN
# ==========================================

def main():
    st.set_page_config(page_title="Leitor NFe Tabular", layout="wide")
    st.title("Sistema de Gestão de Notas Fiscais (Motor Tabular)")
    
    menu = st.sidebar.radio("Navegação", ["Processar Nota", "Balanço (Dashboard)"])
    
    if menu == "Processar Nota":
        processa_nota()
    else:
        balanco_nota_fiscal()

if __name__ == "__main__":
    main()