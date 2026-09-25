"""
Extração de dados de Contratos, Termos Aditivos e Notas de Empenho via IA (Gemini) e regex em PDFs.
"""
import re
import os
import json
import tempfile
import numpy as np
from markitdown import MarkItDown
from google.genai import types

# Importação do seu client. 
# IMPORTANTE: Garanta que em nfe_app/config.py você tem algo como:
# load_dotenv()
# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) se a chave existir.
from nfe_app.config import client

def limpar_json_ia(texto_resposta):
    """Garante que resquícios de markdown (```json) não quebrem o json.loads"""
    texto = texto_resposta.strip()
    if texto.startswith("```"):
        texto = re.sub(r'^```(?:json)?\s*', '', texto)
        texto = re.sub(r'\s*```$', '', texto)
    return texto.strip()

def extrair_dados_via_ia_gemini(bytes_arquivo, nome_arquivo, tipo_doc="contrato"):
    if client is None:
        raise Exception("Cliente Gemini (IA) não inicializado. Verifique se a GEMINI_API_KEY foi carregada no config.py!")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(bytes_arquivo)
        temp_caminho = temp_file.name

    try:
        md = MarkItDown()
        resultado_md = md.convert(temp_caminho)
        texto_markdown = resultado_md.text_content
        
        if tipo_doc == "contrato":
            prompt = f"""
            Analise este documento markdown de um contrato. 
            Retorne APENAS um JSON válido com as seguintes chaves (se não achar algo, retorne vazio ""):
            - "numero_contrato": string
            - "numero_contrato_spaguas": string
            - "processo_sei": string
            - "valor_contrato": float
            - "vigencia_meses": int
            
            Documento:\n{texto_markdown}
            """
        else:
            prompt = f"""
            Analise este documento markdown de um termo aditivo. Retorne APENAS um JSON válido com as seguintes chaves:
            - "numero_contrato": string (código PRODESP ou normal do contrato principal, ex: PD024453. Deixe vazio se não houver)
            - "numero_contrato_spaguas": string (código SP Águas do contrato principal, ex: 2022/23/00007.3. Deixe vazio se não houver)
            - "valor_aditivo": float (apenas números e ponto decimal)
            - "vigencia_aditivo": int (apenas os meses EXTRAS adicionados. Se não houver prorrogação, retorne 0)
            
            Documento:\n{texto_markdown}
            """
            
        resposta = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        
        os.remove(temp_caminho)
        
        # Limpeza preventiva e conversão para dicionário
        texto_limpo = limpar_json_ia(resposta.text)
        return json.loads(texto_limpo)

    except Exception as e:
        if os.path.exists(temp_caminho):
            os.remove(temp_caminho)
        raise Exception(f"Falha na IA ({tipo_doc}): {str(e)}")


def extrair_dados_empenho_via_ia(bytes_arquivo, nome_arquivo):
    if client is None:
        raise Exception("Cliente Gemini (IA) não inicializado. Verifique se a GEMINI_API_KEY foi carregada no config.py!")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(bytes_arquivo)
        temp_caminho = temp_file.name

    try:
        md = MarkItDown()
        resultado_md = md.convert(temp_caminho)
        texto_markdown = resultado_md.text_content
        
        prompt = f"""
        Analise este documento markdown de uma Nota de Empenho (NE) do sistema SIAFISICO/SP. 
        Retorne APENAS um JSON válido com as seguintes chaves (se não achar algo, retorne vazio ""):
        - "numero_empenho": string (O número da NE. Ex: 2024NE01390)
        - "processo_sei": string (O número do processo SEI. Geralmente fica no campo 'Local de Entrega' com o formato 137.00015391/2024-05)
        - "cnpj_credor": string (Pode ser o CNPJ normal ou o código UG no campo 'CNPJ/CPF/UG'. Ex: 533284)
        - "numero_contrato": string (Número do contrato. Ex: 2024CT00379)
        - "natureza_despesa": string (Código de 8 dígitos sob 'Natureza Despesa'. Ex: 33904090)
        - "fonte_recurso": string (Código de 9 dígitos sob 'Fonte'. Ex: 150140001)
        - "valor_empenhado": float (O 'Valor do Empenho R$'. Apenas números e ponto, ex: 1464.90)
        - "ug": string (O código UGR de 6 dígitos. Ex: 262103)
        - "assunto": string (A descrição, serviço ou assunto principal do empenho)
        
        Documento:\n{texto_markdown}
        """
            
        resposta = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", 
                temperature=0.1
            )
        )
        
        os.remove(temp_caminho)
        
        texto_limpo = limpar_json_ia(resposta.text)
        return json.loads(texto_limpo)

    except Exception as e:
        if os.path.exists(temp_caminho): 
            os.remove(temp_caminho)
        raise Exception(f"Falha na IA para NE: {str(e)}")


def extrair_numero_contrato_spaguas(texto_geral, df_ocr=None):
    if not texto_geral and df_ocr is not None and not df_ocr.empty:
        texto_geral = " ".join(df_ocr['text'].dropna().astype(str))
    if not texto_geral: return ""
    
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    match_spaguas = re.search(r'CONTRATO\s*(?:N[ºo°]?)?\s*(\d{4}/\d{2}/\d+\.\d+)', texto_limpo, re.IGNORECASE)
    if match_spaguas:
        return match_spaguas.group(1).strip()
        
    match_alt = re.search(r'CONTRATO\s*(?:N[ºo°]?)?\s*([0-9]{4}/[0-9]{2}/[0-9\.]+)', texto_limpo, re.IGNORECASE)
    if match_alt:
        return match_alt.group(1).strip().rstrip('.,-')
        
    return ""

def extrair_numero_contrato_pdf(texto_geral, df_ocr=None):
    if not texto_geral and df_ocr is not None and not df_ocr.empty:
        texto_geral = " ".join(df_ocr['text'].dropna().astype(str))
    if not texto_geral: return ""
    
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    match_prodesp = re.search(r'CONTRATO\s+PRODESP\s+N[ºo°]?\s*([A-Z0-9\/\-\.]+)', texto_limpo, re.IGNORECASE)
    if match_prodesp:
        return match_prodesp.group(1).strip().rstrip('.,-')
        
    match_geral_pd = re.search(r'CONTRATO\s+([A-Z]*\d+[A-Z0-9\-\.]*)', texto_limpo, re.IGNORECASE)
    if match_geral_pd:
        cap = match_geral_pd.group(1).strip().rstrip('.,-')
        if any(char.isdigit() for char in cap): return cap

    match_classico = re.search(r'N[uú]mero\s+do\s+Contrato\s*[:\-]?\s*([A-Z0-9\-\.\/]+)', texto_limpo, re.IGNORECASE)
    if match_classico:
        return match_classico.group(1).strip().rstrip('.,-')
    return ""

def extrai_processo_sei(texto_geral, df_ocr=None):
    if not texto_geral and df_ocr is not None and not df_ocr.empty:
        texto_geral = " ".join(df_ocr['text'].dropna().astype(str))
    if not texto_geral: 
        return ""
    
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    padroes = [
        r'PROCESSO.*?\b(\d{3,7}\.\d{5,9}/\d{4}-\d{2})\b',
        r'\b(\d{3,7}\.\d{5,9}/\d{4}-\d{2})\b'
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
    return ""

def extrair_valor_contrato_pdf(texto_geral, df_ocr=None):
    if not texto_geral and df_ocr is not None and not df_ocr.empty:
        texto_geral = " ".join(df_ocr['text'].dropna().astype(str))
    if not texto_geral: return 0.0
    
    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    
    match_inicial = re.search(r'Valor\s+inicial\s*[:\-]?\s*(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto_limpo, re.IGNORECASE)
    if match_inicial:
        try:
            val = float(match_inicial.group(1).replace('.', '').replace(',', '.'))
            if val > 0: return val
        except ValueError: pass

    padroes = [
        r'Valor\s+(?:Total|Global|do\s+Contrato)\s*[:\-]?\s*(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Valor\s+Estimado\s*[:\-]?\s*(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'Valor\s+Global\s+do\s+Contrato\s*[:\-]?\s*(?:R\$|RS)?\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
        r'(?:R\$|RS)\s*(\d{1,3}(?:\.\d{3})*,\d{2}).{0,30}?(?:valor\s+total|global\s+do\s+contrato)'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                if val > 0: return val
            except ValueError: continue
                
    valores = re.findall(r'(?:R\$|RS)\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto_limpo, re.IGNORECASE)
    if valores:
        valores_float = [float(v.replace('.', '').replace(',', '.')) for v in valores if v]
        if valores_float: return float(np.max(valores_float))
    return 0.0

def extrair_vigencia_contrato_pdf(texto_geral, df_ocr=None):
    if not texto_geral and df_ocr is not None and not df_ocr.empty:
        texto_geral = " ".join(df_ocr['text'].dropna().astype(str))
    if not texto_geral: return "Não identificada"

    texto_limpo = re.sub(r'\s+', ' ', texto_geral)
    padroes = [
        r'vig[êe]ncia\s+da\s+contrata[çc][ãa]o\s+[ée]\s+de\s+(\d+\s*(?:\([A-ZÀ-Úa-z\s]+\)\s*)?(?:meses|mês|mes|ano[s]?|dia[s]?))',
        r'(?:Prazo|Per[íi]odo|Termo)\s+de\s+Vig[êe]ncia.{0,40}?(?<!\d)(\d+\s*(?:\([A-ZÀ-Úa-z\s]+\)\s*)?(?:meses|mês|mes|ano[s]?|dia[s]?))',
        r'Vig[êe]ncia\s*(?:de\s+)?[:\-]?\s*(\d+\s*(?:\([A-ZÀ-Úa-z\s]+\)\s*)?(?:meses|mês|mes|ano[s]?|dia[s]?))'
    ]
    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match: return match.group(1).strip()

    try:
        if df_ocr is not None and not df_ocr.empty:
            tokens = [str(t).strip() for t in df_ocr['text'].dropna().tolist() if str(t).strip()]
            for i in range(len(tokens)):
                token_lower = tokens[i].lower()
                if 'vigência' in token_lower or 'vigencia' in token_lower:
                    trecho = " ".join(tokens[i+1:min(i+9, len(tokens))])
                    match_trecho = re.search(r'(\d+\s*(?:\([A-ZÀ-Úa-z\s]+\)\s*)?(?:meses|mês|mes|ano[s]?|dia[s]?))', trecho, re.IGNORECASE)
                    if match_trecho: return match_trecho.group(1).strip()
    except Exception: pass
    return "Não identificada"

def converter_vigencia_para_inteiro(texto_vigencia):
    if not texto_vigencia or texto_vigencia == "Não identificada": return 0
    match_numero = re.search(r'\d+', str(texto_vigencia))
    if match_numero: return int(match_numero.group(0))
    return 0