"""Agregaciones de resultados para dashboards (#4, #7, #15).

No crea modelos ni migraciones: solo lee Resultado + PuntajeDimension.
"""

from django.utils import timezone


VARK_DIMS = ("V", "A", "R", "K")
PERSONALIDAD_DIMS = ("E", "I", "S", "N", "T", "F", "J", "P")
PERSONALIDAD_PARES = (
    ("E", "I"),
    ("S", "N"),
    ("T", "F"),
    ("J", "P"),
)


def _puntajes_por_resultado(resultados):
    """Devuelve {resultado_id: {dim: puntaje}} en una sola consulta."""
    mapa = {r.id: {} for r in resultados}
    for p in (
        # Import local para evitar ciclos en tiempo de import.
        # Resultado ya viene filtrado; pedimos sus puntajes.
        __import__("apps.results.models", fromlist=["PuntajeDimension"])
        .PuntajeDimension.objects
        .filter(resultado_id__in=list(mapa.keys()))
        .values("resultado_id", "dimension", "puntaje")
    ):
        mapa[p["resultado_id"]][p["dimension"]] = p["puntaje"]
    return mapa


def _tipo_personalidad(puntajes):
    """'INTJ' o con '?' en la letra empatada (p. ej. 'ENF?')."""
    letras = []
    for a, b in PERSONALIDAD_PARES:
        va = puntajes.get(a, 0)
        vb = puntajes.get(b, 0)
        if va == vb:
            letras.append("?")
        else:
            letras.append(a if va > vb else b)
    return "".join(letras)


def _vark_dominantes(puntajes):
    """Lista de dimensiones VARK con el puntaje máximo (puede haber empate)."""
    if not puntajes:
        return []
    maximo = max(puntajes.values())
    if maximo == 0:
        return []
    return [d for d, v in puntajes.items() if v == maximo]


def _estadisticas_dimensiones(puntajes_por_resultado, dimensiones):
    """[{dimension, promedio, total, min, max}] con 2 decimales."""
    filas = []
    for dim in dimensiones:
        valores = [
            p.get(dim, 0)
            for p in puntajes_por_resultado.values()
        ]
        n = len(valores)
        total = sum(valores) if valores else 0
        filas.append({
            "dimension": dim,
            "promedio": round(total / n, 2) if n else 0.0,
            "total": total,
            "min": min(valores) if valores else 0,
            "max": max(valores) if valores else 0,
        })
    return filas


def _n_estudiantes_y_grupos(resultados):
    estudiantes = set()
    grupos = set()
    for r in resultados:
        evaluacion = r.evaluacion
        estudiantes.add(evaluacion.estudiante_id)
        grupos.add(evaluacion.estudiante.grupo_id)
    return len(estudiantes), len(grupos)


def agregar_resultados(resultados, alcance, tipo):
    """Construye el payload uniforme para los tres alcances."""
    resultados = list(resultados)
    puntajes_por_resultado = _puntajes_por_resultado(resultados)

    if tipo == "VARK":
        dimensiones = _estadisticas_dimensiones(puntajes_por_resultado, VARK_DIMS)
        distribucion = {d: 0 for d in VARK_DIMS}
        for puntajes in puntajes_por_resultado.values():
            for d in _vark_dominantes(puntajes):
                distribucion[d] += 1
        tipos_personalidad = None
    else:
        dimensiones = _estadisticas_dimensiones(
            puntajes_por_resultado, PERSONALIDAD_DIMS
        )
        distribucion = None
        tipos_personalidad = {}
        for puntajes in puntajes_por_resultado.values():
            t = _tipo_personalidad(puntajes)
            tipos_personalidad[t] = tipos_personalidad.get(t, 0) + 1

    n_estudiantes, n_grupos = _n_estudiantes_y_grupos(resultados)

    return {
        "alcance": alcance,
        "tipo": tipo,
        "n_resultados": len(resultados),
        "n_estudiantes": n_estudiantes,
        "n_grupos": n_grupos,
        "dimensiones": dimensiones,
        "distribucion_dominante": distribucion,
        "tipos_personalidad": tipos_personalidad,
        "generado_en": timezone.now().isoformat(),
    }