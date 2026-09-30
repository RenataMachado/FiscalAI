"""
Funções de suporte: conversão de arquivos (PDF/imagem), leitura de QR Code e OCR tabular.
"""
import os
import io
import cv2
import numpy as np
import pytesseract
from pytesseract import Output
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image

def convert_nota_fiscal(arquivos_bytes, tipo):
    if tipo == "pdf":
        caminho_poppler = os.getenv("POPPLER_PATH") 
        return convert_from_bytes(arquivos_bytes, poppler_path=caminho_poppler)
    elif tipo in ["png", "jpg", "jpeg"]:
        img = Image.open(io.BytesIO(arquivos_bytes))
        return [img]
    return []

def ler_qrcode_imagem(imagem_pill):
    imagem_np = np.array(imagem_pill)
    detector = cv2.QRCodeDetector()
    texto, bbox, _ = detector.detectAndDecode(imagem_np)
    if texto:
        return [texto]
    return []

def extrair_dados_ocr_tabular(lista_imagens):
    df_completo = pd.DataFrame()
    for img in lista_imagens:
        df_pagina = pytesseract.image_to_data(img, lang="por", output_type=Output.DATAFRAME)
        df_completo = pd.concat([df_completo, df_pagina], ignore_index=True)
    
    if df_completo.empty or 'text' not in df_completo.columns:
        return pd.DataFrame(columns=['text', 'block_num', 'line_num', 'conf'])

    df_completo = df_completo.dropna(subset=['text'])
    # O Tesseract às vezes devolve números como int/float; convertemos tudo para texto
    df_completo['text'] = df_completo['text'].astype(str)
    df_completo = df_completo[df_completo['text'].str.strip() != '']
    df_completo['conf'] = pd.to_numeric(df_completo['conf'], errors='coerce').fillna(0)
    df_completo = df_completo[df_completo['conf'] > 30]
    return df_completo.reset_index(drop=True)

def reconstruir_texto_corrido(df_ocr):
    if df_ocr is None or df_ocr.empty:
        return ""
    return " ".join(df_ocr['text'].astype(str))
