"""
Funções de extração de dados de Notas de Empenho (padrão SIAFÍSICO SP) via regex.
"""
import re

def extrair_numero_empenho(texto_geral):
    match = re.search(r'\b(\d{4}NE\d{5})\b', texto_geral, re.IGNORECASE)
    if match: return match.group(1).upper()
    return ""

def extrai_fonte_empenho(texto_geral):
    match = re.search(r'\b(15\d{7})\b', texto_geral)
    if match: return match.group(1)
    return ""

def extrai_cod_unico_empenho(texto_geral):
    match = re.search(r'(?:UG|Unidade\s*Gestora)[^\d]*(\d{6})', texto_geral, re.IGNORECASE)
    if match: return match.group(1)
    return ""

def extrai_processo_sei_empenho(texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes = [
        r'SEI\s*[-|:]?\s*(\d{3,7}[.,\s]?\d{5,9}[/\s]?\d{4}[-\s]?\d{2})',
        r'Local\s+de\s+Entrega.*?(?:SEI)?\s*[-|:]?\s*(\d{3,7}[.,\s]?\d{5,9}[/\s]?\d{4}[-\s]?\d{2})',
        r'\b(\d{3,7}[.,\s]?\d{5,9}[/\s]?\d{4}[-\s]?\d{2})\b'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match: 
            sei_sujo = match.group(1)
            sei_limpo = re.sub(r'\s+', '', sei_sujo).replace(',', '.')
            return sei_limpo
    return ""

def extrai_cnpj_empenho(texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    match_ug = re.search(r'CNPJ/CPF/UG\s*\|\s*(\d{5,14})', texto_limpo, re.IGNORECASE)
    if match_ug: return match_ug.group(1).strip()
    
    cnpjs = re.findall(r'\d{2}[.,\s]?\d{3}[.,\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}', texto_limpo)
    if cnpjs: 
        cnpj_corrigido = cnpjs[0].replace(',', '.')
        return re.sub(r'[^\d\.\/\-]', '', cnpj_corrigido)
    
    return ""

def extrai_numero_contrato_empenho(texto_geral):
    match = re.search(r'N[ºo°]?\s*Contrato\s*\|?\s*([A-Z0-9]{8,12})', texto_geral, re.IGNORECASE)
    if match: return match.group(1).strip()
    
    match_alt = re.search(r'\b(\d{4}CT\d{5})\b', texto_geral, re.IGNORECASE)
    if match_alt: return match_alt.group(1).strip()
    
    return ""

def extrai_natureza_empenho(texto_geral):
    match = re.search(r'\b([34]\d{7})\b', texto_geral)
    if match: return match.group(1)
    return ""

def extrai_valor_empenho(texto_geral):
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    match = re.search(r'Valor do Empenho R\$[\s\|]*([\d\.,]+)', texto_limpo, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace('.', '').replace(',', '.'))
        except ValueError: pass
        
    valores = re.findall(r'(?:R\$|RS)\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto_limpo, re.IGNORECASE)
    if valores:
        import numpy as np
        return float(np.max([float(v.replace('.', '').replace(',', '.')) for v in valores if v]))
        
    return 0.0

def extrai_assunto_empenho(texto_geral):
    match = re.search(r'Descrição\s*[:\-]?\s*(.+?)(?:\n|$)', texto_geral, re.IGNORECASE | re.DOTALL)
    if match: return match.group(1).strip()
    return ""

def extrai_ug_empenho(texto_geral):
    match = re.search(r'UGR\s*[:\-]?\s*(\d{6})', texto_geral, re.IGNORECASE)
    if match: return match.group(1)
    return ""
