import re
import pytesseract
import streamlit as st
import cv2
from pyzbar.pyzbar import decode
from pdf2image import convert_from_bytes
import numpy as np

def processa_nota():
    st.title("Sistema de Leitura de Notas Fiscais")
    arquivo_upload = st.file_uploader("Faça o upload da nota fiscal (pdf ou imagem)", type=["pdf", "png", "jpg", "jpeg"])
    if arquivo_upload is not None:
        st.success("Arquivo enviado com sucesso!")
        
        # Lendo os bytes do arquivo enviado
        bytes_arquivo = arquivo_upload.read()
        
        # Retorna os dados para serem usados no restante do app
        return {
            "nome": arquivo_upload.name,
            "tipo": arquivo_upload.type,
            "bytes": bytes_arquivo,
            "numero_nfe": None,
            "data_emissao": None,
            "vencimento": None,
            "cnpj_emitente": None,
            "cnpj_pagador": None,
            "valor_total": None,
            "valor_ir": None,
        }
    
    return None
    
# testw
def convert_nota_fiscal(arquivos_bytes):
   imagens= convert_from_bytes(arquivos_bytes)
   return imagens

def ler_qrcode_imagem(imagem_pill):
    imagem_np = np.array(imagem_pill)
    # Converte para escala de cinza para melhorar a precisão da leitura
    cinza = cv2.cvtColor(imagem_np, cv2.COLOR_RGB2GRAY)
    
    # Executa a leitura do QR Code
    codigos = decode(cinza)
    
    resultados = []
    for codigo in codigos:
        dados_qrcode = codigo.data.decode('utf-8')
        resultados.append(dados_qrcode)
        
    return resultados

def armazena_info():
    pass

def balanco_nota_fiscal():
    pass


def numero_nfe():
    pass

def emissao_nota():
    pass

def vencimento():
    pass

def cnpj_emitente():
    pass

def cnpj_pagador():
    pass

def valor_total(l):
    pass

def valor_ir():
    pass

def valor_liquido():
    pass

def main():
    
    dados_arquivo = processa_nota()
    
    if dados_arquivo is not None:
        tipo = dados_arquivo["nome"].lower().split(".")[-1]

        if tipo in ["pdf", "png", "jpg", "jpeg"]:
            imagens = convert_nota_fiscal(dados_arquivo["bytes"])
        else:
            st.error("Arquivo não compatível.")

    if dados_arquivo is None:
        return
    

if __name__ == "__main__":
    main()