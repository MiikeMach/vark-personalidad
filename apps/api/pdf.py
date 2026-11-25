"""Generación de PDFs de ficha técnica (#14).

No crea modelos ni migraciones: solo lee Resultado + PuntajeDimension.
Usa reportlab (platypus) para evitar dependencias nativas.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from apps.api.aggregations import (
    agregar_resultados,
    _tipo_personalidad,
    _vark_dominantes,
    VARK_DIMS,
    PERSONALIDAD_DIMS,
)

# Etiquetas legibles por dimensión.
ETIQUETAS_DIM = {
    "V": "Visual",
    "A": "Auditivo",
    "R": "Lectura/Escritura",
    "K": "Kinestésico",
    "E": "Extroversión",
    "I": "Introversión",
    "S": "Sensación",
    "N": "Intuición",
    "T": "Pensamiento",
    "F": "Sentimiento",
    "J": "Juicio",
    "P": "Percepción",
}


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloFicha",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SubtituloFicha",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=8,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Cuerpo",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
    ))
    return styles


def _tabla_datos(filas, styles):
    tabla = Table(
        [[Paragraph(f"<b>{k}</b>", styles["Cuerpo"]),
          Paragraph(str(v), styles["Cuerpo"])] for k, v in filas],
        colWidths=[4.5 * cm, 11 * cm],
    )
    tabla.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    return tabla


def _tabla_puntajes(resultado, styles):
    dims = VARK_DIMS if resultado.evaluacion.cuestionario.tipo == "VARK" \
        else PERSONALIDAD_DIMS
    puntajes = {p.dimension: p.puntaje for p in resultado.puntajes.all()}
    filas = [["Dimensión", "Etiqueta", "Puntaje"]]
    for d in dims:
        filas.append([d, ETIQUETAS_DIM.get(d, d), str(puntajes.get(d, 0))])
    tabla = Table(filas, colWidths=[3 * cm, 9 * cm, 3.5 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tabla


def _ficha_resultado_story(resultado, styles):
    """Story (lista de flowables) para una ficha individual."""
    ev = resultado.evaluacion
    estudiante = ev.estudiante
    grupo = estudiante.grupo
    cuestionario = ev.cuestionario

    story = [
        Paragraph("Ficha técnica de resultado", styles["TituloFicha"]),
        Paragraph(
            f"Resultado #{resultado.id} — "
            f"generado {resultado.calculado_en.isoformat()}",
            styles["Cuerpo"],
        ),
        Spacer(1, 0.3 * cm),

        Paragraph("Datos del alumno", styles["SubtituloFicha"]),
        _tabla_datos([
            ("Matrícula", estudiante.matricula),
            ("Nombres", estudiante.nombres),
            ("Apellidos", estudiante.apellidos),
            ("Correo", estudiante.correo or "—"),
            ("Grupo", f"{grupo.clave} — {grupo.nombre}"),
        ], styles),
        Spacer(1, 0.3 * cm),

        Paragraph("Instrumento", styles["SubtituloFicha"]),
        _tabla_datos([
            ("Cuestionario", cuestionario.titulo),
            ("Tipo", cuestionario.get_tipo_display()),
            ("Evaluación", f"#{ev.id}"),
            ("Iniciada", ev.iniciada_en.isoformat()),
            ("Finalizada", ev.finalizada_en.isoformat() if ev.finalizada_en else "—"),
        ], styles),
        Spacer(1, 0.3 * cm),

        Paragraph("Conteos", styles["SubtituloFicha"]),
        _tabla_datos([
            ("Preguntas contestadas", resultado.preguntas_contestadas),
            ("Preguntas omitidas", resultado.preguntas_omitidas),
        ], styles),
        Spacer(1, 0.3 * cm),

        Paragraph("Puntajes por dimensión", styles["SubtituloFicha"]),
        _tabla_puntajes(resultado, styles),
        Spacer(1, 0.3 * cm),
    ]

    # Resumen específico por tipo.
    puntajes = {p.dimension: p.puntaje for p in resultado.puntajes.all()}
    if cuestionario.tipo == "VARK":
        dominantes = _vark_dominantes(puntajes)
        etiquetas = [ETIQUETAS_DIM.get(d, d) for d in dominantes]
        resumen = (
            "Perfil dominante: " + " + ".join(etiquetas)
            if etiquetas else "Sin dimensión dominante (todos los puntajes en 0)."
        )
    else:
        tipo_mbti = _tipo_personalidad(puntajes)
        resumen = f"Tipo de personalidad (Jung/MBTI): {tipo_mbti}."

    story.append(Paragraph("Resumen", styles["SubtituloFicha"]))
    story.append(Paragraph(resumen, styles["Cuerpo"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Interpretación", styles["SubtituloFicha"]))
    story.append(Paragraph(
        resultado.interpretacion or "—",
        styles["Cuerpo"],
    ))
    return story


def _portada_agregada_story(alcance, tipo, agregado, styles):
    story = [
        Paragraph("Ficha técnica agregada", styles["TituloFicha"]),
        Paragraph(
            f"Alcance: {alcance} — Tipo: {tipo} — "
            f"Generado: {agregado['generado_en']}",
            styles["Cuerpo"],
        ),
        Spacer(1, 0.3 * cm),

        Paragraph("Resumen", styles["SubtituloFicha"]),
        _tabla_datos([
            ("Resultados incluidos", agregado["n_resultados"]),
            ("Estudiantes", agregado["n_estudiantes"]),
            ("Grupos", agregado["n_grupos"]),
        ], styles),
        Spacer(1, 0.3 * cm),

        Paragraph("Promedios por dimensión", styles["SubtituloFicha"]),
    ]

    filas = [["Dimensión", "Etiqueta", "Promedio", "Total", "Mín", "Máx"]]
    for fila in agregado["dimensiones"]:
        d = fila["dimension"]
        filas.append([
            d,
            ETIQUETAS_DIM.get(d, d),
            f"{fila['promedio']:.2f}",
            str(fila["total"]),
            str(fila["min"]),
            str(fila["max"]),
        ])
    tabla = Table(filas, colWidths=[2 * cm, 6 * cm, 2.5 * cm, 2 * cm, 1.5 * cm, 1.5 * cm])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 0.3 * cm))

    if tipo == "VARK":
        dist = agregado.get("distribucion_dominante") or {}
        story.append(Paragraph("Distribución de perfiles dominantes", styles["SubtituloFicha"]))
        story.append(_tabla_datos(
            [(f"{d} — {ETIQUETAS_DIM.get(d, d)}", n) for d, n in dist.items()],
            styles,
        ))
    else:
        tipos = agregado.get("tipos_personalidad") or {}
        story.append(Paragraph("Distribución de tipos (Jung/MBTI)", styles["SubtituloFicha"]))
        story.append(_tabla_datos(
            [(t, n) for t, n in sorted(tipos.items())],
            styles,
        ))

    return story


def _render(story, titulo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=titulo,
    )
    doc.build(story)
    return buffer.getvalue()


def construir_pdf_individual(resultado) -> bytes:
    styles = _styles()
    story = _ficha_resultado_story(resultado, styles)
    return _render(story, f"Ficha resultado {resultado.id}")


def construir_pdf_multiple(resultados, alcance, tipo) -> bytes:
    """Portada agregada + una ficha por resultado."""
    styles = _styles()
    resultados = list(resultados)
    agregado = agregar_resultados(resultados, alcance, tipo)

    story = _portada_agregada_story(alcance, tipo, agregado, styles)

    if resultados:
        story.append(PageBreak())
        for i, resultado in enumerate(resultados):
            if i > 0:
                story.append(PageBreak())
            story.extend(_ficha_resultado_story(resultado, styles))
    else:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
            "No se encontraron resultados para los filtros indicados.",
            styles["Cuerpo"],
        ))

    return _render(story, f"Ficha {alcance} {tipo}")