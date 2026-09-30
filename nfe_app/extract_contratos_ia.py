"""
Extração de dados de Contratos, Termos Aditivos e Notas de Empenho via IA (Claude, da Anthropic) e regex em PDFs.
"""
import re
import os
import json
import tempfile
import numpy as np
import anthropic
from markitdown import MarkItDown

# Cliente da Anthropic criado em nfe_app/config.py (fica None se a ANTHROPIC_API_KEY não estiver no .env).
from nfe_app.config import client

# Modelo da Claude configurável pelo .env (ANTHROPIC_MODEL=...).
# Modelos antigos são aposentados de tempos em tempos; assim você troca sem mexer no código.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5").strip()

# Modelos de reserva (opcional), separados por vírgula no .env.
# Ex.: ANTHROPIC_MODELOS_RESERVA=claude-sonnet-5
# Se o modelo principal continuar sobrecarregado mesmo depois das novas tentativas, o sistema tenta estes.
ANTHROPIC_MODELOS_RESERVA = [
    m.strip() for m in os.getenv("ANTHROPIC_MODELOS_RESERVA", "").split(",") if m.strip()
]

# "Esforço" da IA: low | medium | high. Quanto menor, mais rápido e barato (a IA "pensa" menos).
# Para deixar de enviar esse parâmetro, deixe vazio no .env: ANTHROPIC_EFFORT=
ANTHROPIC_EFFORT = os.getenv("ANTHROPIC_EFFORT", "medium").strip()

# Limite de tokens da resposta (raciocínio + JSON). O JSON é pequeno; a folga é para o raciocínio.
# Você só paga pelo que for realmente usado, não pelo limite.
ANTHROPIC_MAX_TOKENS = 8192

# Sobre "temperature": o Claude Sonnet 5.5 NÃO aceita temperature/top_p/top_k diferentes do
# padrão (a API devolve erro 400). Por isso esse parâmetro não é enviado. Quem garante a
# resposta previsível é o "molde" JSON (structured outputs, ver _schema_json abaixo): a API
# obriga o modelo a devolver exatamente as chaves e os tipos definidos, sem texto extra.

# Erros passageiros, que valem a pena tentar de novo / trocar de modelo:
# 408 = tempo esgotado | 409 = conflito | 429 = muitas requisições
# 500/502/503/504 = erro no servidor | 529 = API da Anthropic sobrecarregada
CODIGOS_TEMPORARIOS = {408, 409, 429, 500, 502, 503, 504, 529}


def limpar_json_ia(texto_resposta):
    """Garante que resquícios de markdown (```json) não quebrem o json.loads"""
    texto = (texto_resposta or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r'^```(?:json)?\s*', '', texto)
        texto = re.sub(r'\s*```$', '', texto)
    return texto.strip()


def _pdf_para_markdown(bytes_arquivo):
    """Converte o PDF em texto markdown. O arquivo temporário é SEMPRE apagado no final."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(bytes_arquivo)
        temp_caminho = temp_file.name
    try:
        md = MarkItDown()
        return md.convert(temp_caminho).text_content or ""
    finally:
        if os.path.exists(temp_caminho):
            os.remove(temp_caminho)


def _schema_json(campos):
    """
    Monta o "molde" (JSON Schema) que a Claude é OBRIGADA a seguir na resposta.
    campos: {"nome_do_campo": "string" | "number" | "integer"}
    Todos os campos são obrigatórios e nenhum campo extra é permitido.
    Obs.: campos numéricos não encontrados voltam como 0 (e não ""); os conversores
    das páginas (converter_float / converter_int) tratam os dois casos do mesmo jeito.
    """
    return {
        "type": "object",
        "properties": {nome: {"type": tipo} for nome, tipo in campos.items()},
        "required": list(campos),
        "additionalProperties": False,
    }


SCHEMA_CONTRATO = _schema_json({
    "numero_contrato": "string",
    "numero_contrato_spaguas": "string",
    "processo_sei": "string",
    "valor_contrato": "number",
    "vigencia_meses": "integer",
})

SCHEMA_ADITIVO = _schema_json({
    "numero_contrato": "string",
    "numero_contrato_spaguas": "string",
    "valor_aditivo": "number",
    "vigencia_aditivo": "integer",
})

SCHEMA_EMPENHO = _schema_json({
    "numero_empenho": "string",
    "processo_sei": "string",
    "cnpj_credor": "string",
    "numero_contrato": "string",
    "natureza_despesa": "string",
    "fonte_recurso": "string",
    "valor_empenhado": "number",
    "ug": "string",
    "assunto": "string",
})


def _erro_temporario(erro):
    """
    True se o erro for passageiro (servidor ocupado / limite de uso / conexão caiu),
    ou seja, vale a pena tentar outro modelo de reserva.
    """
    if isinstance(erro, anthropic.APIConnectionError):  # sem internet ou tempo esgotado
        return True
    return getattr(erro, "status_code", None) in CODIGOS_TEMPORARIOS


def _mensagem_amigavel(erro, modelo):
    """Traduz os erros mais comuns da Anthropic para uma mensagem que diz como resolver."""
    codigo = getattr(erro, "status_code", None)
    texto = str(erro)
    if codigo == 401:
        return "Chave da Anthropic inválida. Confira a ANTHROPIC_API_KEY no arquivo .env."
    if codigo == 404:
        return f"Modelo '{modelo}' não encontrado. Confira ANTHROPIC_MODEL no arquivo .env."
    if "credit balance" in texto.lower():
        return "A conta da Anthropic está sem créditos. Adicione créditos no Console da Anthropic."
    return texto


def _chamar_modelo(modelo, conteudo, schema):
    """
    Faz UMA chamada à Claude.
    conteudo: o prompt (texto) ou uma lista de blocos (ex.: arquivo + prompt, usado nas notas fiscais).
    schema:   o molde JSON que a resposta deve seguir.
    """
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if ANTHROPIC_EFFORT:
        output_config["effort"] = ANTHROPIC_EFFORT

    resposta = client.messages.create(
        model=modelo,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        messages=[{"role": "user", "content": conteudo}],
        output_config=output_config,
    )

    if resposta.stop_reason == "refusal":
        raise ValueError("A IA se recusou a processar este documento.")
    if resposta.stop_reason == "max_tokens":
        raise ValueError("A resposta da IA foi cortada (limite de tokens atingido).")

    # A resposta pode trazer blocos de "raciocínio" antes do texto; o JSON fica no bloco de texto.
    texto = next((bloco.text for bloco in resposta.content if bloco.type == "text"), "")
    dados = json.loads(limpar_json_ia(texto))
    # Às vezes a IA devolve uma lista com um único objeto
    if isinstance(dados, list):
        dados = dados[0] if dados else {}
    if not isinstance(dados, dict):
        raise ValueError("A IA não retornou um JSON no formato esperado.")

    # Consumo REAL de tokens, informado pela própria Anthropic em cada resposta.
    # Fica guardado na chave "_tokens" (as páginas ignoram essa chave ao ler os campos).
    dados["_tokens"] = _ler_uso_tokens(resposta, modelo)
    return dados


def _ler_uso_tokens(resposta, modelo):
    """
    Extrai os contadores de tokens da resposta da Claude (campo usage):
      - entrada:    o que foi enviado (prompt + documento)
      - raciocinio: a Anthropic não informa esse número separado; os tokens de raciocínio
                    já vêm somados na "saida" (e são cobrados como saída). Fica 0 para
                    manter o mesmo formato que a tela de consumo espera.
      - saida:      a resposta em si (o JSON) + o raciocínio
      - total:      entrada + saída
    """
    uso = getattr(resposta, "usage", None)

    def pegar(campo):
        return int(getattr(uso, campo, 0) or 0) if uso else 0

    entrada = (pegar("input_tokens")
               + pegar("cache_creation_input_tokens")
               + pegar("cache_read_input_tokens"))
    saida = pegar("output_tokens")
    return {"modelo": modelo, "entrada": entrada, "raciocinio": 0, "saida": saida, "total": entrada + saida}


def _perguntar_ia(conteudo, schema):
    """
    Chama a Claude e devolve o JSON já convertido em dicionário.
    - As novas tentativas automáticas (esperando um pouco mais a cada vez) são feitas pelo
      próprio SDK da Anthropic (quantidade definida em config.py por ANTHROPIC_TENTATIVAS).
    - Se mesmo assim a API continuar ocupada, passa para os modelos de reserva (se houver no .env).
    - Erros que NÃO são temporários (chave errada, modelo inexistente, sem créditos) param na hora.
    """
    ultimo_erro = None
    for modelo in [ANTHROPIC_MODEL] + ANTHROPIC_MODELOS_RESERVA:
        try:
            return _chamar_modelo(modelo, conteudo, schema)
        except Exception as erro:
            if not _erro_temporario(erro):
                raise Exception(_mensagem_amigavel(erro, modelo)) from erro
            ultimo_erro = erro
            print(f"[IA] {modelo} continua indisponível ({erro}). Tentando o próximo modelo, se houver.")
    raise Exception(
        "Os servidores da Anthropic estão sobrecarregados no momento (tentamos várias vezes). "
        f"Tente novamente em alguns minutos. Detalhe: {ultimo_erro}"
    )


def _verificar_cliente():
    if client is None:
        raise Exception("Cliente da Anthropic (IA) não inicializado. Verifique se a ANTHROPIC_API_KEY está no arquivo .env!")


def extrair_dados_via_ia(bytes_arquivo, nome_arquivo, tipo_doc="contrato"):
    _verificar_cliente()
    try:
        texto_markdown = _pdf_para_markdown(bytes_arquivo)
        if len(texto_markdown.strip()) < 30:
            # PDF escaneado (só imagem): não há texto para a IA ler -> cai no OCR
            raise ValueError("PDF sem texto selecionável (provavelmente escaneado).")

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
        schema = SCHEMA_CONTRATO if tipo_doc == "contrato" else SCHEMA_ADITIVO
        return _perguntar_ia(prompt, schema)
    except Exception as e:
        raise Exception(f"Falha na IA ({tipo_doc}): {str(e)}")


# Nome antigo mantido para que as páginas (contratos.py e aditivos.py) continuem funcionando sem alteração.
extrair_dados_via_ia_gemini = extrair_dados_via_ia


def extrair_dados_empenho_via_ia(bytes_arquivo, nome_arquivo):
    _verificar_cliente()
    try:
        texto_markdown = _pdf_para_markdown(bytes_arquivo)
        if len(texto_markdown.strip()) < 30:
            raise ValueError("PDF sem texto selecionável (provavelmente escaneado).")

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
        return _perguntar_ia(prompt, SCHEMA_EMPENHO)
    except Exception as e:
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