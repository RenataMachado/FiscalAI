"""
Funções de extração de dados de Notas Fiscais (NFS-e) a partir do texto/OCR.
"""
import re
import numpy as np

def numero_nfe(df_ocr, texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes = [
        r'N[uú]mero\s+da\s+Nota[\s/|]*S[eé]rie.{0,100}?(\d+(?:\.\d+)*)',
        r'N[uú]mero\s+da\s+Nota.{0,100}?(\d+(?:\.\d+)+)', 
        r'N[uú]mero\s+da\s+NFS-e.{0,100}?(\d+(?:\.\d+)*)',
        r'NFS-e\s*n?[ºo]?\s*.{0,50}?(\d+(?:\.\d+)*)'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            numero_str = match.group(1).replace('.', '')
            if len(numero_str) >= 3:
                return numero_str

    match_prox = re.search(r'NFS-e.*?(\b\d{4,15}\b)', texto_limpo, re.IGNORECASE)
    if match_prox:
        return match_prox.group(1).replace('.', '')
    return ""

def razao_social_emitente(df_ocr, texto_geral):
    try:
        if df_ocr is not None and not df_ocr.empty:
            palavras = df_ocr['text'].dropna().astype(str).str.strip().tolist()
            palavras = [p for p in palavras if p]
            texto_completo = " ".join(palavras).upper()
            
            if re.search(r'SIMPRESS', texto_completo):
                return "SIMPRESS COMERCIO LOCAÇÃO SERVIÇOS LTDA"
                
            if re.search(r'CIA\s+DE\s+PROCESSAMENTO\s+DE\s+DADOS\s+DO\s+ESTADO\s+DE\s+S[ÃA]O\s+PAULO', texto_completo):
                return "CIA DE PROCESSAMENTO DE DADOS DO ESTADO DE SÃO PAULO - PRODESP"

            for i, palavra in enumerate(palavras):
                p_upper = palavra.upper().replace('.', '')
                if p_upper in ['LTDA', 'SA', 'S/A', 'ME', 'EPP', 'EIRELI']:
                    inicio = max(0, i - 6)
                    trecho = palavras[inicio:i+1]
                    trecho_limpo = []
                    for t in trecho:
                        if t.upper() in ['CNPJ', 'CPF', 'ENDEREÇO', 'CEP', 'INSCRIÇÃO'] or re.search(r'\d{4,}', t):
                            trecho_limpo = [] 
                        else:
                            trecho_limpo.append(t)
                    nome_final = " ".join(trecho_limpo).strip('.,-:/ ')
                    if len(nome_final) > 5: return nome_final

                elif p_upper in ['CIA', 'COMPANHIA', 'INSTITUTO', 'FUNDAÇÃO']:
                    fim = min(len(palavras), i + 9)
                    trecho = palavras[i:fim]
                    trecho_limpo = []
                    for t in trecho:
                        if t.upper() in ['CNPJ', 'CPF', 'ENDEREÇO', 'MUNICÍPIO'] or re.search(r'\d{4,}', t): break 
                        trecho_limpo.append(t)
                    nome_final = " ".join(trecho_limpo).strip('.,-:/ ')
                    if len(nome_final) > 5: return nome_final
    except Exception:
        pass

    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes_fallback = [
        r'Raz[ãa]o\s+Social\s*[:\-]?\s*([A-ZÀ-Ú0-9\s\.\-\&]{5,60})',
        r'Nome\s+Empresarial\s*[:\-]?\s*([A-ZÀ-Ú0-9\s\.\-\&]{5,60})',
        r'PRESTADOR\s+DE\s+SERVI[ÇC]OS?\s*[:\-]?\s*([A-ZÀ-Ú0-9\s\.\-\&]{5,60})'
    ]
    for padrao in padroes_fallback:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            nome = match.group(1)
            nome = re.split(r'(?i)\b(?:CNPJ|CPF|Inscrição|Endereço)\b', nome)[0].strip().rstrip('.,-:/')
            if len(nome) > 4: return nome

    return "NÃO IDENTIFICADO"

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
        if match: return match.group(1)
    return ""

def vencimento(texto_geral):
    padroes = [
        r'Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})', 
        r'Data de Vencimento\s*[:]?\s*(\d{2}/\d{2}/\d{4})' 
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE)
        if match: return match.group(1)
    return ""

def cnpj_emitente(texto_geral):
    match = re.search(r'(?:EMITENTE|PRESTADOR|FORNECEDOR).*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', texto_geral, re.IGNORECASE | re.DOTALL)
    if match: return match.group(1)
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto_geral)
    return cnpjs[0] if len(cnpjs) > 0 else ""

def cnpj_pagador(texto_geral):
    padroes = [
        r'TOMADOR\s*/\s*ADQUIRENTE.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'TOMADOR\s+DO\s+SERVI[ÇC]O.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'TOMADOR.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', 
        r'ADQUIRENTE.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'DESTINAT[ÁA]RIO.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        r'PAGADOR.*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_geral, re.IGNORECASE | re.DOTALL)
        if match: return match.group(1)
    cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', texto_geral)
    return cnpjs[1] if len(cnpjs) > 1 else ""

def valor_iss(df_ocr, texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padrao_prioritario = r'Valor\s+do\s+ISSQN\s*\(R\$\)\s*2[,\.]00[^\d]*?(\d{1,3}(?:\.\d{3})*,\d{2})'
    match_prio = re.search(padrao_prioritario, texto_limpo, re.IGNORECASE)
    if match_prio:
        try:
            val = float(match_prio.group(1).replace('.', '').replace(',', '.'))
            if val > 0: return val
        except ValueError: pass

    try:
        if df_ocr is not None and not df_ocr.empty:
            textos_linhas = [str(t).strip() for t in df_ocr['text'].tolist() if str(t).strip()]
            texto_unido_linhas = " ".join(textos_linhas)
            match_linhas = re.search(r'Valor\s+do\s+ISSQN\s*\(R\$\)\s*2[,\.]00[^\d]*?(\d{1,3}(?:\.\d{3})*,\d{2})', texto_unido_linhas, re.IGNORECASE)
            if match_linhas:
                val = float(match_linhas.group(1).replace('.', '').replace(',', '.'))
                if val > 0: return val
    except Exception: pass

    padroes_secundarios = [
        r'ISSQN{0,2}\s*Apurado[\s\w:.-]{0,30}?(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'ISS[QN]{0,2}\s*(?:Retido)?\s*(?:na)?\s*(?:Fonte)?[\s\w:.-]{0,50}?(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Imposto\s+Sobre\s+Serviço[s]?[\s\w:.-]{0,50}?(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'ISS\s*-\s*Retenção[\s\w:.-]{0,30}?(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})'
    ]
    for padrao in padroes_secundarios:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                if val > 0 and val != 2.0 and val != 5.0: return val
            except ValueError: continue
    return 0.0

def valor_total(df_ocr, texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes_fortes = [
        r'Valor\s+do\s+Servi[çc]o.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'BC\s+ISS[QN]{2}.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+TOTAL\s+DA\s+NFS-e.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'Resultado\s+da\s+Presta[çc][ãa]o\s+do\s+Servi[çc]o.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+DA\s+OPERA[ÇC][ÃA]O\s*(?:/|-)?\s*SERVI[ÇC]O.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'Valor\s+do\s+Servi[çc]o.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'BC\s+ISS[QN]{2}.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+TOTAL\s+DA\s+NFS-e.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'Resultado\s+da\s+Presta[çc][ãa]o\s+do\s+Servi[çc]o.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+DA\s+OPERA[ÇC][ÃA]O\s*(?:/|-)?\s*SERVI[ÇC]O.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})'
    ]
    for padrao in padroes_fortes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                if val > 0: return val
            except ValueError: continue

    valores_com_rs = re.findall(r'(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})', texto_limpo, re.IGNORECASE)
    if valores_com_rs:
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores_com_rs if v]
        if valores_float:
            maior_valor_rs = float(np.max(valores_float))
            if maior_valor_rs > 50.0: return maior_valor_rs

    valores_sem_rs = re.findall(r'(?<!\d)(\d+(?:\.\d{3})*,\d{2})(?!\d)', texto_limpo)
    if valores_sem_rs:
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores_sem_rs if v]
        if valores_float:
            maior_valor_geral = float(np.max(valores_float))
            if maior_valor_geral > 50.0: return maior_valor_geral
    return 0.0

def valor_liquido(df_ocr, texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes = [
        r'VALOR\s+L[ÍI]QUIDO\s+DA\s+NFS-e\s*\+\s*IBS\s*/\s*CBS.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO\s+DA\s+NFS-e.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO\s+DA\s+NFS-e\s*\+\s*IBS\s*/\s*CBS.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO\s+DA\s+NFS-e.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})',
        r'VALOR\s+L[ÍI]QUIDO.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{2})'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                if val > 0: return val
            except ValueError: continue
    return 0.0

def valor_ir(df_ocr, texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    padroes_ir = [
        r'RETENCAO(?:\s+NA)?\s+FONTE\s+IR\s*:\s*(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})(?!\s*%)',
        r'RETEN[ÇC][ÃA]O(?:\s+NA)?\s+FONTE\s+IRRF?\s*[:\-]?\s*(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})(?!\s*%)',
        r'FONTE\s+IR\s*[:\-]?\s*(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})',
        r'IRRF\s*[:\-]?\s*(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})(?!\s*%)',
        r'IRPJ\s*[:\-]?\s*(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})(?!\s*%)', 
        r'\bIR\s*\([R\$]+\).{0,50}?(\d+(?:\.\d{3})*,\d{1,2})', 
        r'IRRF.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'IRPJ.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'Reten[çc][õo]es\s+Federais.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'Total\s+das\s+Reten[çc][õo]es.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'Imposto\s+de\s+Renda.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'RETEN[ÇC][ÃA]O.{0,30}?FONTE\s+IR.{0,200}?(?:R\$|RS)\s*(\d+(?:\.\d{3})*,\d{1,2})',
        r'IRRF.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})',
        r'IRPJ.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})',
        r'Reten[çc][õo]es\s+Federais.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})',
        r'Total\s+das\s+Reten[çc][õo]es.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})',
        r'Imposto\s+de\s+Renda.{0,30}?(?<!\d)(\d+(?:\.\d{3})*,\d{1,2})'
    ]
    
    for padrao in padroes_ir:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                if val > 1.0: return val
            except ValueError: continue
            
    return 0.0

def numero_contrato(texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes = [
        r'CONTRATO(?:\s*[:\-]?\s*)([A-Z]*\d+[A-Z0-9\-\.]*)',
        r'N[uú]mero\s+do\s+Contrato\s*[:\-]?\s*([A-Z0-9\-\.]+)', 
        r'Contrato\s*[:\-]?\s*([A-Z0-9\-\.]+)',            
        r'No\.?\s*do\s*Contrato\s*[:\-]?\s*([A-Z0-9\-\.]+)'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            captura = match.group(1).strip()
            if any(char.isdigit() for char in captura):
                return captura.rstrip('.,-')
    return ""
