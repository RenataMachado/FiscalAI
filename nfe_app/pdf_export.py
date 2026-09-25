"""
Geração do relatório em PDF do balanço de notas fiscais.
"""
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def gerar_pdf_balanco(lista_dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=10, leftMargin=10, topMargin=30, bottomMargin=30)
    
    elementos = []
    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle(
        'TituloPDF',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#005b96'),
        alignment=1, 
        spaceAfter=15
    )
    
    elementos.append(Paragraph("Relatório de Balanço de Notas Fiscais", estilo_titulo))
    elementos.append(Spacer(1, 10))
    
    estilo_cabecalho = ParagraphStyle('CabTabela', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=6.5, textColor=colors.whitesmoke, alignment=1)
    estilo_celula = ParagraphStyle('CellTabela', parent=styles['Normal'], fontName='Helvetica', fontSize=6, textColor=colors.HexColor('#333333'), alignment=1)
    estilo_celula_esquerda = ParagraphStyle('CellEsquerda', parent=styles['Normal'], fontName='Helvetica', fontSize=6, textColor=colors.HexColor('#333333'), alignment=0)
    estilo_celula_direita = ParagraphStyle('CellDireita', parent=styles['Normal'], fontName='Helvetica', fontSize=6, textColor=colors.HexColor('#333333'), alignment=2)

    cabecalho = [
        Paragraph("Empresa", estilo_cabecalho),
        Paragraph("NFE", estilo_cabecalho),
        Paragraph("Contrato", estilo_cabecalho),
        Paragraph("Contrato SP Águas", estilo_cabecalho),
        Paragraph("Processo SEI", estilo_cabecalho),
        Paragraph("Emissão", estilo_cabecalho),
        Paragraph("Vencimento", estilo_cabecalho),
        Paragraph("CNPJ Emitente", estilo_cabecalho),
        Paragraph("Bruto (R$)", estilo_cabecalho),
        Paragraph("ISS (R$)", estilo_cabecalho),
        Paragraph("IRF (R$)", estilo_cabecalho),
        Paragraph("Líquido (R$)", estilo_cabecalho)
    ]
    
    dados_tabela = [cabecalho]
    
    for item in lista_dados:
        v_bruto = f"R$ {item.get('valor_total', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(item.get('valor_total'), (int, float)) else str(item.get('valor_total', ''))
        v_iss = f"R$ {item.get('valor_iss', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(item.get('valor_iss'), (int, float)) else str(item.get('valor_iss', ''))
        v_ir = f"R$ {item.get('valor_ir', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(item.get('valor_ir'), (int, float)) else str(item.get('valor_ir', ''))
        v_liq = f"R$ {item.get('valor_liquido', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if isinstance(item.get('valor_liquido'), (int, float)) else str(item.get('valor_liquido', ''))

        linha = [
            Paragraph(str(item.get("Arquivo", "")), estilo_celula_esquerda),
            Paragraph(str(item.get("numero_nfe", "")), estilo_celula),
            Paragraph(str(item.get("numero_contrato", "")), estilo_celula),
            Paragraph(str(item.get("numero_contrato_spaguas", "")), estilo_celula), 
            Paragraph(str(item.get("processo_sei", "")), estilo_celula), 
            Paragraph(str(item.get("data_emissao", "")), estilo_celula),
            Paragraph(str(item.get("vencimento", "")), estilo_celula),
            Paragraph(str(item.get("cnpj_emitente", "")), estilo_celula),
            Paragraph(v_bruto, estilo_celula_direita),
            Paragraph(v_iss, estilo_celula_direita),
            Paragraph(v_ir, estilo_celula_direita),
            Paragraph(v_liq, estilo_celula_direita)
        ]
        dados_tabela.append(linha)
        
    tabela = Table(dados_tabela, colWidths=[110, 35, 65, 65, 75, 45, 45, 70, 50, 45, 45, 50])
    
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#005b96')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d3d3d3')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
    ]))
    
    elementos.append(tabela)
    doc.build(elementos)
    buffer.seek(0)
    return buffer
