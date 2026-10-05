# -*- coding: utf-8 -*-
"""
Identidade visual do sistema, no padrão da apresentação da SP Águas:
azul-marinho, azul-petróleo, ciano, verde e azul; títulos com serifa (Cambria),
texto em Calibri, rótulos em letras espaçadas, cartões claros arredondados,
as três faixas da marca e ondas no rodapé.

Uso (já feito no app.py e na tela de login):
    from nfe_app import tema
    tema.aplicar_tema()          # uma vez, logo no começo do app
    tema.rotulo("Balanço")       # texto pequeno e espaçado acima de um título
"""
import base64
import html
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import streamlit as st

# Paleta tirada da apresentação
MARINHO = "#041B2D"        # fundo das capas
MARINHO_2 = "#0A3350"      # painéis escuros
TITULO = "#0B2A3F"         # títulos sobre fundo claro
PETROLEO = "#0F6E8C"       # cor principal (botões, rótulos)
CIANO = "#22B8CF"          # números grandes, destaques
VERDE = "#00A859"          # 1º lugar, faixa verde
AZUL = "#0057D9"           # faixa azul
CELESTE = "#4FB3F6"        # faixa azul-clara
GELO = "#EEF5F7"           # fundo dos cartões
GELO_2 = "#E1EEF2"
TEXTO_SUAVE = "#5B6B78"
FUNDO = "#F7FAFB"

# ---------------------------------------------------------------------------
# TAMANHOS (mude aqui; o resto do arquivo usa estes valores)
# ---------------------------------------------------------------------------
# Letras do sistema inteiro. O padrão do Streamlit é 16px. Quase todos os tamanhos
# do visual são proporcionais a este (unidade "rem"): mudando só ele, tudo acompanha.
TAMANHO_TEXTO = "18px"
# Letras dos botões do menu lateral (Processador Nota, Balanço...)
TAMANHO_MENU = "1.08rem"
# Largura da marca de ondas no topo das páginas
LARGURA_MARCA_TOPO = "150px"
# Altura do logo da SP Águas na tela de login
ALTURA_LOGO_LOGIN = "150px"

# Imagem da marca usada no topo das páginas (fica na pasta "images" do projeto)
MARCA_PNG = Path(__file__).resolve().parent.parent / "images" / "marca_sp_aguas_alta_resolucao.png"

FONTE_TITULO = 'Cambria, Caladea, Georgia, "Times New Roman", serif'
FONTE_TEXTO = 'Calibri, Carlito, "Segoe UI", "Helvetica Neue", Arial, sans-serif'


# ---------------------------------------------------------------------------
# Desenhos (SVG)
# ---------------------------------------------------------------------------
def marca_svg(largura=150):
    """As três faixas curvas da marca (verde, azul e azul-claro)."""
    faixas = ""
    for i, cor in enumerate((VERDE, AZUL, CELESTE)):
        y = i * 15
        faixas += (f'<path fill="{cor}" d="M4 {18 + y} C 70 {3 + y}, 150 {5 + y}, 216 {17 + y} '
                   f'C 150 {11 + y}, 70 {12 + y}, 4 {27 + y} Z"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 62" width="{largura}" '
            f'role="img" aria-label="SP Águas">{faixas}</svg>')


def _ondas_escuras():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 240" preserveAspectRatio="none">'
        '<path d="M0 78 C 360 40, 760 108, 1100 62 S 1440 30, 1440 30" fill="none" '
        'stroke="rgba(255,255,255,0.28)" stroke-width="1.5"/>'
        '<path fill="#0A3B52" d="M0 100 C 320 72, 760 128, 1440 84 L1440 240 L0 240 Z"/>'
        '<path fill="#0C5168" d="M0 128 C 420 104, 860 156, 1440 116 L1440 240 L0 240 Z"/>'
        '<path fill="#0B5F5A" d="M0 156 C 460 136, 900 186, 1440 148 L1440 240 L0 240 Z"/>'
        '<path fill="#0B5C84" d="M0 182 C 420 166, 920 206, 1440 176 L1440 240 L0 240 Z"/>'
        '<path fill="#17699A" d="M0 208 C 520 196, 960 224, 1440 202 L1440 240 L0 240 Z"/>'
        '</svg>'
    )


def _ondas_claras():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 120" preserveAspectRatio="none">'
        '<path d="M0 46 C 380 30, 760 64, 1100 40 S 1440 28, 1440 28" fill="none" '
        'stroke="#9ED8E3" stroke-width="1.5"/>'
        '<path fill="#E3F3F6" d="M0 62 C 420 42, 840 84, 1440 52 L1440 120 L0 120 Z"/>'
        '<path fill="#D2ECF1" d="M0 88 C 480 72, 900 104, 1440 82 L1440 120 L0 120 Z"/>'
        '</svg>'
    )


def _como_url_css(svg):
    return f'url("data:image/svg+xml,{quote(svg)}")'


@lru_cache(maxsize=4)
def _imagem_base64(caminho):
    caminho = Path(caminho)
    if not caminho.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(caminho.read_bytes()).decode("ascii")


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def _css():
    ondas_escuras = _como_url_css(_ondas_escuras())
    ondas_claras = _como_url_css(_ondas_claras())
    return f"""
<style>
:root {{
  --sp-marinho: {MARINHO}; --sp-marinho-2: {MARINHO_2}; --sp-titulo: {TITULO};
  --sp-petroleo: {PETROLEO}; --sp-ciano: {CIANO}; --sp-verde: {VERDE};
  --sp-gelo: {GELO}; --sp-gelo-2: {GELO_2}; --sp-suave: {TEXTO_SUAVE};
}}

/* Tamanho base das letras (veja TAMANHO_TEXTO no começo do arquivo) */
html {{ font-size: {TAMANHO_TEXTO}; }}

/* Fundo claro com a onda do rodapé, como nos slides de conteúdo */
.stApp {{
  font-family: {FONTE_TEXTO};
  background: {ondas_claras} bottom / 100% 110px no-repeat fixed, {FUNDO};
}}
.stApp::after {{
  content: "SP Águas  •  Sistema de Gestão de Notas Fiscais";
  position: fixed; right: 2rem; bottom: 0.9rem; z-index: 0; pointer-events: none;
  font: 0.78rem {FONTE_TEXTO}; color: var(--sp-suave);
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 2.2rem; padding-bottom: 7rem; }}

/* Textos */
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] {{ font-family: {FONTE_TEXTO}; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{
  font-family: {FONTE_TITULO} !important; color: var(--sp-titulo); font-weight: 700; letter-spacing: -0.01em;
}}

/* Texto das páginas: rótulos dos campos e legendas um pouco maiores */
[data-testid="stWidgetLabel"] p {{ font-size: 1rem; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{ font-size: 0.95rem; }}

/* Rótulo pequeno e espaçado acima dos títulos ("P R O C E S S A R  N O T A") */
.sp-rotulo {{
  font: 700 0.76rem {FONTE_TEXTO}; letter-spacing: 0.32em; text-transform: uppercase;
  color: var(--sp-petroleo); margin: 0 0 -0.6rem 0;
}}

/* Topo das páginas: título com serifa e as três faixas à direita */
.sp-topo {{ display: flex; align-items: center; justify-content: space-between; gap: 1.5rem;
  padding-bottom: 1.1rem; margin-bottom: 1.4rem; border-bottom: 1px solid var(--sp-gelo-2); }}
.sp-topo .sp-rotulo {{ margin: 0 0 0.35rem 0; font-size: 0.7rem; }}
.sp-topo h1 {{ margin: 0; padding: 0; font-size: 2.1rem; line-height: 1.15; }}
.sp-topo svg {{ flex: none; }}
.sp-topo .sp-topo-marca {{ width: {LARGURA_MARCA_TOPO}; height: auto; flex: none; }}

/* Botões arredondados */
.stButton > button, [data-testid="stFormSubmitButton"] > button, [data-testid="stDownloadButton"] > button {{
  border-radius: 10px; font-family: {FONTE_TEXTO}; font-weight: 600;
}}

/* Indicadores (st.metric) como os cartões claros dos slides */
[data-testid="stMetric"] {{
  background: var(--sp-gelo); border-radius: 14px; padding: 1rem 1.2rem; border-left: 4px solid var(--sp-petroleo);
}}
[data-testid="stMetricLabel"] p {{
  font-size: 0.72rem !important; letter-spacing: 0.18em; text-transform: uppercase; color: var(--sp-petroleo) !important;
  font-weight: 700;
}}
[data-testid="stMetricValue"] {{ font-family: {FONTE_TITULO}; color: var(--sp-titulo); }}

/* Avisos e expansores com cantos arredondados */
[data-testid="stAlert"] {{ border-radius: 12px; }}
[data-testid="stExpander"] details {{ border-radius: 12px; }}

/* ---------- Barra lateral: painel escuro com ondas, como o "Sumário" ---------- */
[data-testid="stSidebar"] {{
  background: {ondas_escuras} bottom / 100% 190px no-repeat,
              linear-gradient(160deg, {MARINHO} 0%, {MARINHO_2} 55%, #0B4A63 100%);
}}
[data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #E6F1F5; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #9FC3D1; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.15); }}
[data-testid="stSidebarContent"] {{ padding-bottom: 170px; }}
.sp-lateral-rotulo {{ font: 700 0.8rem {FONTE_TEXTO}; letter-spacing: 0.3em; text-transform: uppercase;
  color: var(--sp-ciano); margin: 0.4rem 0 0.3rem 0; }}

/* Botões de navegação: transparentes; a página atual fica destacada em ciano */
[data-testid="stSidebar"] .stButton > button {{
  background: transparent; border: 1px solid transparent; color: #E6F1F5; justify-content: flex-start;
  border-radius: 10px;
}}
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] .stButton > button p {{ font-size: {TAMANHO_MENU}; }}
[data-testid="stSidebar"] .stButton > button {{ padding-top: 0.55rem; padding-bottom: 0.55rem; }}
[data-testid="stSidebar"] .stButton > button:hover {{ background: rgba(34,184,207,0.12); border-color: rgba(34,184,207,0.35); color: #FFFFFF; }}
[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
  background: rgba(34,184,207,0.18); border: 1px solid rgba(34,184,207,0.45);
  box-shadow: inset 3px 0 0 var(--sp-ciano); color: #FFFFFF;
}}
[data-testid="stSidebar"] [data-testid="stAlert"] {{ background: rgba(255,255,255,0.08); border-left: 3px solid #F5A524; }}

/* Logo da barra lateral centralizado */
[data-testid="stSidebar"] [data-testid="stImage"],
[data-testid="stSidebar"] [data-testid="stImageContainer"] {{ display: flex; justify-content: center; margin: 0 auto; }}

/* Cartão do usuário logado: um bloco só dele, centralizado */
[data-testid="stSidebar"] .st-key-sp_cartao_usuario {{
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.14);
  border-radius: 16px; padding: 1.2rem 1rem 1rem 1rem; gap: 0.7rem;
  box-shadow: 0 10px 28px rgba(0,0,0,0.18);
}}
[data-testid="stSidebar"] .sp-usuario {{
  display: flex; flex-direction: column; align-items: center; text-align: center; gap: 0.2rem; padding-bottom: 0.9rem;
}}
[data-testid="stSidebar"] .sp-avatar {{
  width: 60px; height: 60px; border-radius: 50%; margin-bottom: 0.5rem;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, {CIANO}, {PETROLEO}); color: #FFFFFF;
  font: 700 1.3rem {FONTE_TEXTO}; letter-spacing: 0.04em;
  box-shadow: 0 0 0 3px rgba(34,184,207,0.25);
}}
[data-testid="stSidebar"] .sp-usuario-nome {{ font: 700 1.15rem {FONTE_TEXTO}; color: #FFFFFF; line-height: 1.25; }}
[data-testid="stSidebar"] .sp-usuario-email {{ font-size: 0.88rem; color: #9FC3D1; word-break: break-all; }}
[data-testid="stSidebar"] .sp-usuario-perfil {{
  margin-top: 0.45rem; padding: 0.18rem 0.75rem; border-radius: 999px;
  border: 1px solid rgba(34,184,207,0.45); color: {CIANO};
  font: 700 0.7rem {FONTE_TEXTO}; letter-spacing: 0.22em; text-transform: uppercase;
}}
/* Botão Sair dentro do cartão: centralizado e com borda discreta */
[data-testid="stSidebar"] .st-key-sp_cartao_usuario .stButton > button {{
  justify-content: center; border: 1px solid rgba(255,255,255,0.18);
}}

/* ---------- Tela de entrada: painel de capa à esquerda ---------- */
.sp-capa {{
  position: relative; overflow: hidden; border-radius: 22px; min-height: 560px;
  padding: 3rem 2.8rem 12rem 2.8rem; color: #FFFFFF;
  background: {ondas_escuras} bottom / 100% 210px no-repeat,
              radial-gradient(circle at 85% 15%, rgba(34,184,207,0.18), transparent 45%),
              linear-gradient(150deg, {MARINHO} 0%, {MARINHO_2} 55%, #0B4A63 100%);
}}
.sp-capa .sp-rotulo {{ color: #7FD3E2; margin: 2.2rem 0 1rem 0; font-size: 0.7rem; }}
.sp-capa h1 {{ font-family: {FONTE_TITULO} !important; color: #FFFFFF !important; font-size: 2.7rem; line-height: 1.12; margin: 0 0 1rem 0; padding: 0; }}
.sp-capa p {{ color: #CFE6EE; font-size: 1.08rem; line-height: 1.5; max-width: 30rem; margin: 0; }}
.sp-capa img {{ height: {ALTURA_LOGO_LOGIN}; width: auto; }}

/* Tela de entrada em TELA CHEIA: o fundo azul com as ondas ocupa a janela inteira
   (sem margem branca), e a coluna do formulário vira um cartão branco por cima dele.
   (Se o navegador não entender ":has", fica o visual claro padrão, sem quebrar nada.) */
.stApp:has(.sp-cartao-login) {{
  background-color: {MARINHO};
  background-image: {ondas_escuras},
                    radial-gradient(circle at 80% 10%, rgba(34,184,207,0.20), transparent 45%),
                    linear-gradient(150deg, {MARINHO} 0%, {MARINHO_2} 55%, #0B4A63 100%);
  background-repeat: no-repeat;
  background-position: bottom, center, center;
  background-size: 100% 240px, cover, cover;
  background-attachment: fixed;
}}
.stApp:has(.sp-cartao-login) [data-testid="stMainBlockContainer"],
.stApp:has(.sp-cartao-login) .block-container {{
  max-width: 100%; padding: 2rem 6vw 0 6vw;
}}
/* Botão "Deploy" e menu do canto superior visíveis sobre o fundo escuro */
.stApp:has(.sp-cartao-login) [data-testid="stToolbar"] * {{ color: #E6F1F5; }}
[data-testid="stHorizontalBlock"]:has(> div .sp-cartao-login) {{
  background: none; box-shadow: none; border-radius: 0;
  padding: 0 0 210px 0;            /* espaço para as ondas no pé da tela */
  min-height: calc(100vh - 4rem); gap: 4rem; align-items: center;
}}
[data-testid="stHorizontalBlock"]:has(> div .sp-cartao-login) .sp-capa {{
  background: none; min-height: 0; padding: 0; border-radius: 0; overflow: visible;
}}
[data-testid="stHorizontalBlock"]:has(> div .sp-cartao-login) > div:has(.sp-cartao-login) {{
  background: #FFFFFF; border-radius: 18px; padding: 1.4rem 2.2rem 2rem 2.2rem;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.28);
}}
.sp-cartao-login {{ display: block; height: 0; }}
/* Na tela de entrada, o texto do rodapé sai (o painel azul já ocupa a tela) */
.stApp:has(.sp-cartao-login)::after {{ display: none; }}
</style>
"""


# ---------------------------------------------------------------------------
# Funções usadas pelas telas
# ---------------------------------------------------------------------------
def aplicar_tema():
    """Injeta o visual em todas as telas. Chame uma vez, logo depois do st.set_page_config."""
    st.markdown(_css(), unsafe_allow_html=True)


def rotulo(texto):
    """Texto pequeno, em maiúsculas e espaçado (fica acima de um título)."""
    st.markdown(f'<div class="sp-rotulo">{texto}</div>', unsafe_allow_html=True)


def topo_da_pagina(titulo, rotulo_texto="Governo do Estado de São Paulo  •  SEMIL  •  SP Águas"):
    """Faixa de topo das páginas internas: rótulo + título com serifa + a marca da SP Águas."""
    imagem = _imagem_base64(str(MARCA_PNG))
    # Se o arquivo não existir, continua usando o desenho antigo (não quebra a tela)
    marca = f'<img src="{imagem}" alt="SP Águas" class="sp-topo-marca">' if imagem else marca_svg(130)
    st.markdown(
        f'<div class="sp-topo"><div><div class="sp-rotulo">{rotulo_texto}</div><h1>{titulo}</h1></div>'
        f'{marca}</div>',
        unsafe_allow_html=True,
    )


NOMES_PERFIS = {"admin": "Administrador", "processador": "Processador", "consulta": "Consulta"}


def _iniciais(nome):
    """'Renata Karoline Ruela Machado' -> 'RM'; e-mail -> primeira letra."""
    partes = [p for p in str(nome).replace("@", " ").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1 or "@" in str(nome):
        return partes[0][0].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def cartao_usuario(nome, email, perfil):
    """Conteúdo do cartão do usuário na barra lateral (iniciais, nome, e-mail e perfil)."""
    # html.escape: nome e e-mail vêm do formulário "Pedir acesso", que qualquer pessoa preenche.
    # Sem isso, alguém poderia enviar um "nome" com código HTML/JavaScript.
    st.markdown(
        '<div class="sp-usuario">'
        f'<div class="sp-avatar">{html.escape(_iniciais(nome))}</div>'
        f'<div class="sp-usuario-nome">{html.escape(str(nome))}</div>'
        f'<div class="sp-usuario-email">{html.escape(str(email))}</div>'
        f'<div class="sp-usuario-perfil">{html.escape(NOMES_PERFIS.get(perfil, str(perfil)))}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def rotulo_lateral(texto):
    st.sidebar.markdown(f'<div class="sp-lateral-rotulo">{texto}</div>', unsafe_allow_html=True)


def marcar_cartao_login():
    """Marca a coluna do formulário de entrada para ela virar o cartão branco dentro do painel azul."""
    st.markdown('<span class="sp-cartao-login"></span>', unsafe_allow_html=True)


def painel_capa(logo_branco=None):
    """Painel escuro da tela de entrada, no estilo da capa da apresentação."""
    imagem = _imagem_base64(str(logo_branco)) if logo_branco else ""
    topo = f'<img src="{imagem}" alt="SP Águas">' if imagem else marca_svg(150)
    st.markdown(
        '<div class="sp-capa">'
        f'{topo}'
        '<div class="sp-rotulo">Governo do Estado de São Paulo  •  SEMIL  •  SP Águas</div>'
        '<h1>Gestão de<br>Notas Fiscais</h1>'
        '<p>Leitura de notas fiscais, contratos e empenhos, com acompanhamento de saldo e vigência.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
