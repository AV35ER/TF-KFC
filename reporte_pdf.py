"""Construcción del informe académico A4 de traducción DSL → SQL."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer


NOTA_ACADEMICA = (
    "La traducción SQL constituye una representación académica. No se ejecuta contra una "
    "base de datos real ni establece conexión con los sistemas internos de KFC"
)
GRAMATICA = (
    "S' -> PEDIDO\nPEDIDO -> ITEMS pago\nITEMS -> ITEMS ITEM | ITEM\n"
    "ITEM -> producto cantidad"
)


def _registrar_fuentes():
    if "Vera" in pdfmetrics.getRegisteredFontNames():
        return "Vera", "Vera-Bold"
    import reportlab
    from pathlib import Path

    fonts = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("KFC-Vera", str(fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("KFC-Vera-Bold", str(fonts / "VeraBd.ttf")))
    return "KFC-Vera", "KFC-Vera-Bold"


def generar_pdf(texto_original, pedidos):
    """Devuelve bytes de un PDF A4; las consultas se presentan, nunca se ejecutan."""
    normal_font, bold_font = _registrar_fuentes()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="Reporte de traducción del DSL", author="Analizador de Pedidos KFC",
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "KfcTitle", parent=base["Title"], fontName=bold_font, fontSize=19,
        leading=24, textColor=colors.HexColor("#c8102e"), alignment=TA_CENTER,
        spaceAfter=10,
    )
    heading = ParagraphStyle(
        "KfcHeading", parent=base["Heading2"], fontName=bold_font, fontSize=13,
        leading=17, textColor=colors.HexColor("#c8102e"), spaceBefore=10, spaceAfter=5,
        keepWithNext=True,
    )
    body = ParagraphStyle(
        "KfcBody", parent=base["BodyText"], fontName=normal_font, fontSize=9.5,
        leading=13, spaceAfter=5, wordWrap="CJK",
    )
    small = ParagraphStyle("KfcSmall", parent=body, fontSize=8, leading=11)
    code_style = ParagraphStyle(
        "KfcCode", parent=base["Code"], fontName=normal_font, fontSize=8,
        leading=11, backColor=colors.HexColor("#f6f2ef"),
        borderColor=colors.HexColor("#ddd2cb"), borderWidth=.5, borderPadding=7,
        leftIndent=3, rightIndent=3, spaceBefore=3, spaceAfter=8,
    )
    story = [
        Paragraph("Reporte de traducción del DSL", title),
        Paragraph(
            "Proyecto académico para analizar pedidos escritos en un lenguaje específico de dominio "
            "(DSL) inspirado en el registro de pedidos de un restaurante. La aplicación no se conecta "
            "a sistemas operativos de KFC.", body,
        ),
        Paragraph("Descripción del proceso", heading),
        Paragraph(
            "DSL -> análisis léxico -> análisis sintáctico -> árbol sintáctico -> análisis semántico "
            "-> transpilación a SQL -> reporte PDF.", body,
        ),
        Paragraph("DSL original", heading),
        Preformatted(escape(texto_original or ""), code_style, maxLineLength=88),
        Paragraph("Gramática aplicada", heading),
        Preformatted(escape(GRAMATICA), code_style),
    ]

    for pedido in pedidos:
        tokens = pedido.get("tokens", [])
        tokens_txt = ", ".join(
            f"{token.get('token', 'DESCONOCIDO')}({token.get('lexema', '')})"
            for token in tokens
        ) or "Sin tokens identificados."
        estado_lexico = "Correcto" if pedido.get("fase") != "léxica" else "Error"
        estado_sintaxis = "Correcto" if pedido.get("sintaxis_ok") else "Error / no ejecutado"
        sem = pedido.get("semantico")
        estado_semantico = (
            "Correcto" if sem and sem.get("valida")
            else "Error / no ejecutado" if sem
            else "No ejecutado: el pedido no superó las etapas previas"
        )
        story.extend([
            Paragraph(f"Pedido de la línea {pedido.get('linea', '?')}", heading),
            Paragraph(f"DSL: <b>{escape(pedido.get('texto', ''))}</b>", body),
            Paragraph(f"Tokens identificados: {escape(tokens_txt)}", body),
            Paragraph(f"Análisis léxico: {estado_lexico}", body),
            Paragraph(f"Análisis sintáctico: {estado_sintaxis}", body),
            Paragraph(f"Análisis semántico: {escape(estado_semantico)}", body),
            Paragraph("Resumen del árbol sintáctico", heading),
            Paragraph(escape(pedido.get("traduccion", {}).get("resumen_ast", "No disponible.")), small),
        ])
        traduccion = pedido.get("traduccion", {})
        if pedido.get("valida") and traduccion.get("sql"):
            story.extend([
                Paragraph("Clasificación: Transpilador", body),
                Paragraph("Lenguaje de destino: SQL", body),
                Paragraph("SQL generado (demostrativo)", heading),
                Preformatted(escape(traduccion["sql"]), code_style, maxLineLength=88),
                Paragraph("Resultado final: Válido; pasó las fases léxica, sintáctica y semántica.", body),
            ])
        else:
            fase = pedido.get("fase") or "desconocida"
            motivo = pedido.get("error") or traduccion.get("motivo") or "No superó las validaciones."
            story.extend([
                Paragraph(f"Traducción no generada. Fase del error: {escape(fase)}.", body),
                Paragraph(f"Motivo: {escape(motivo)}", body),
                Paragraph("SQL: no generado.", body),
                Paragraph("Resultado final: Rechazado.", body),
            ])
        story.append(Spacer(1, 5))

    story.extend([
        Paragraph("Clasificación de la transformación", heading),
        Paragraph(
            "Se clasifica como transpilación porque transforma el DSL en SQL, otro lenguaje de "
            "nivel similar. No genera código máquina ni ejecuta instrucciones SQL.", body,
        ),
        Paragraph(escape(NOTA_ACADEMICA), small),
    ])

    def numerar_pagina(canvas, documento):
        canvas.saveState()
        canvas.setFont(normal_font, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawRightString(A4[0] - 18 * mm, 11 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=numerar_pagina, onLaterPages=numerar_pagina)
    return buffer.getvalue()
