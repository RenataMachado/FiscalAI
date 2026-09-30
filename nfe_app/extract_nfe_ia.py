"""
Extração de dados de Notas Fiscais de Serviço (NFS-e) via IA (Claude, da Anthropic).

Diferente de contratos/aditivos/empenhos, aqui o arquivo (PDF ou imagem) é enviado
DIRETO para a Claude, que "enxerga" o documento. Assim funciona também com notas
escaneadas e fotos, que não têm texto selecionável.

Usa a mesma rotina de chamada da IA de extract_contratos_ia.py (com novas tentativas
automáticas, modelos de reserva e resposta obrigatoriamente em JSON).
"""
import base64

from nfe_app.extract_contratos_ia import _perguntar_ia, _schema_json, _verificar_cliente

# Tipo de arquivo -> (tipo de bloco que a Claude entende, formato do arquivo)
# PDF vai como "document"; fotos/escaneados em imagem vão como "image".
TIPOS_ARQUIVO = {
    "pdf": ("document", "application/pdf"),
    "png": ("image", "image/png"),
    "jpg": ("image", "image/jpeg"),
    "jpeg": ("image", "image/jpeg"),
}

PROMPT_NFSE = """
Você está lendo uma Nota Fiscal de Serviço Eletrônica (NFS-e) brasileira.
Retorne APENAS um JSON válido com as chaves abaixo.
Se não encontrar algum campo, retorne "" (texto) ou 0 (número). NUNCA invente valores.

- "razao_social_emitente": string (nome/razão social do PRESTADOR do serviço, quem emitiu a nota)
- "numero_nfe": string (número da NFS-e, só dígitos, sem pontos. Ex: 2085204)
- "numero_contrato": string (número do contrato citado na nota, se houver. Ex: PD024453. Senão "")
- "data_emissao": string (data de emissão no formato DD/MM/AAAA)
- "vencimento": string (data de vencimento no formato DD/MM/AAAA, se houver. Senão "")
- "cnpj_emitente": string (CNPJ do PRESTADOR, formato 00.000.000/0000-00)
- "cnpj_pagador": string (CNPJ do TOMADOR do serviço, formato 00.000.000/0000-00)
- "valor_total": number (valor BRUTO do serviço / valor total da nota)
- "valor_iss": number (valor em reais do ISS/ISSQN RETIDO. Não confunda com a alíquota em %)
- "valor_ir": number (valor em reais do IR/IRRF retido na fonte. Não confunda com a alíquota em %)
- "valor_liquido": number (valor LÍQUIDO da nota, depois das retenções)

Regras para números: use ponto como separador decimal e sem separador de milhar.
Exemplo: R$ 1.234,56 -> 1234.56
"""

# Molde JSON que a resposta da IA é obrigada a seguir (mesmas chaves do prompt acima).
SCHEMA_NFSE = _schema_json({
    "razao_social_emitente": "string",
    "numero_nfe": "string",
    "numero_contrato": "string",
    "data_emissao": "string",
    "vencimento": "string",
    "cnpj_emitente": "string",
    "cnpj_pagador": "string",
    "valor_total": "number",
    "valor_iss": "number",
    "valor_ir": "number",
    "valor_liquido": "number",
})


def extrair_dados_nfe_via_ia(bytes_arquivo, nome_arquivo):
    """
    Envia a nota para a Claude e devolve um dicionário com os campos da NFS-e.
    Lança exceção se a IA falhar (a página então usa o OCR como Plano B).
    """
    _verificar_cliente()

    extensao = nome_arquivo.lower().rsplit(".", 1)[-1]
    tipo_arquivo = TIPOS_ARQUIVO.get(extensao)
    if not tipo_arquivo:
        raise ValueError(f"Tipo de arquivo não suportado pela IA: .{extensao}")
    tipo_bloco, tipo_mime = tipo_arquivo

    try:
        # O arquivo vai "embutido" na mensagem, em base64 (texto que representa os bytes)
        arquivo_para_ia = {
            "type": tipo_bloco,
            "source": {
                "type": "base64",
                "media_type": tipo_mime,
                "data": base64.standard_b64encode(bytes_arquivo).decode("utf-8"),
            },
        }
        # Arquivo primeiro, instruções depois (mesma ordem usada antes com o Gemini)
        conteudo = [arquivo_para_ia, {"type": "text", "text": PROMPT_NFSE}]
        return _perguntar_ia(conteudo, SCHEMA_NFSE)
    except Exception as e:
        raise Exception(f"Falha na IA (nota fiscal): {str(e)}")