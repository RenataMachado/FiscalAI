"""
Funções utilitárias de formatação: valores monetários, ISS, CNPJ, datas e cotação de câmbio.
"""
import re
import requests
import streamlit as st

@st.cache_data(ttl=3600)  
def obter_taxas_cambio():
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL,EUR-BRL"
        resposta = requests.get(url, timeout=5)
        if resposta.status_code == 200:
            dados = resposta.json()
            taxa_usd = float(dados['USDBRL']['bid'])
            taxa_eur = float(dados['EURBRL']['bid'])
            return taxa_usd, taxa_eur
    except Exception:
        pass
    
    return 5.00, 5.50

def formata_valor(valor):
    if valor is None or valor == "":
        return valor
        
    if isinstance(valor, (int, float)):
        valor_float = float(valor)
        return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
    if isinstance(valor, str):
        val_str = valor.strip().upper()
        multiplicador = 1.0
        
        taxa_usd, taxa_eur = obter_taxas_cambio()
        
        if 'US$' in val_str or 'USD' in val_str or (val_str.startswith('$') and 'R$' not in val_str):
            multiplicador = taxa_usd
        elif '€' in val_str or 'EUR' in val_str:
            multiplicador = taxa_eur
            
        if val_str.isdigit() and len(val_str) > 2:
            valor_float = (float(val_str) / 100.0) * multiplicador
            return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        limpo = re.sub(r'[^0-9.,-]', '', val_str)
        
        if not limpo:
            return valor 
            
        try:
            if ',' in limpo and '.' in limpo:
                if limpo.rfind(',') > limpo.rfind('.'):
                    limpo = limpo.replace('.', '').replace(',', '.')
                else:
                    limpo = limpo.replace(',', '')
            elif ',' in limpo:
                limpo = limpo.replace(',', '.')
            
            valor_float = float(limpo) * multiplicador
            return f"R$ {valor_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
        except ValueError:
            return valor
            
    return valor

def formata_iss(valor):
    if valor is None or valor == "":
        return "R$ 0,00"
        
    if isinstance(valor, (int, float)):
        val_float = float(valor)
        if val_float <= 0: 
            return "R$ 0,00"
        return f"R$ {val_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
    if isinstance(valor, str):
        val_str = valor.strip().upper()
        limpo = re.sub(r'[^0-9.,-]', '', val_str)
        
        if not limpo:
            return "R$ 0,00"
            
        try:
            if ',' in limpo and '.' in limpo:
                if limpo.rfind(',') > limpo.rfind('.'):
                    limpo = limpo.replace('.', '').replace(',', '.')
                else:
                    limpo = limpo.replace(',', '')
            elif ',' in limpo:
                limpo = limpo.replace(',', '.')
            
            val_float = float(limpo)
            if val_float <= 0: 
                return "R$ 0,00"
            return f"R$ {val_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
        except ValueError:
            return "R$ 0,00"
            
    return "R$ 0,00"

def validar_cnpj(cnpj):
    if not cnpj:
        return False
    limpo = re.sub(r'\D', '', str(cnpj))
    if len(limpo) != 14:
        return False
    return True

def formata_cnpj(cnpj):
    if cnpj is None:
        return ""
    cnpj_limpo = re.sub(r'\D', '', str(cnpj))
    if len(cnpj_limpo) == 14:
        return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"
    return str(cnpj).strip() if cnpj else ""

def formata_data(data_str):
    if not data_str:
        return ""
        
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
