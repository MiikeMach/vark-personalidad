"""Carga datos ficticios en todas las secciones para probar el panel y el sitio.

Uso:
    python manage.py cargar_datos_demo

Crea grupos, estudiantes, un cuestionario VARK y uno de personalidad (con
preguntas y opciones), evaluaciones finalizadas y en curso, respuestas,
resultados y puntajes. Es repetible: no duplica lo que ya existe. Si existen
las cuentas «demo.estudiante» (crear_cuentas_roles), se vincula a un estudiante.
Todos los nombres y datos son inventados.
"""

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assessments.models import Evaluacion
from apps.assessments.services import guardar_respuesta, guardar_respuesta_personalidad
from apps.questionnaires.models import Cuestionario, Opcion, Pregunta
from apps.results.services import finalizar_evaluacion
from apps.students.models import Estudiante, Grupo

GRUPOS = (
    ("1A-2026", "Primero A", True),
    ("2B-2026", "Segundo B", True),
    ("3C-2026", "Tercero C", True),
    ("3C-2025", "Tercero C (ciclo anterior)", False),
)

ESTUDIANTES = (
    # matrícula, nombres, apellidos, grupo, activo
    ("A26-001", "Lucía", "Ramírez Torres", "1A-2026", True),
    ("A26-002", "Mateo", "Hernández Ruiz", "1A-2026", True),
    ("A26-003", "Valentina", "Gómez Salas", "1A-2026", True),
    ("A26-004", "Santiago", "Morales Vega", "1A-2026", True),
    ("A26-005", "Camila", "Flores Ortiz", "1A-2026", True),
    ("B26-001", "Diego", "Castillo Navarro", "2B-2026", True),
    ("B26-002", "Ximena", "Reyes Domínguez", "2B-2026", True),
    ("B26-003", "Emiliano", "Vargas Lozano", "2B-2026", True),
    ("B26-004", "Renata", "Mendoza Ríos", "2B-2026", True),
    ("B26-005", "Leonardo", "Aguilar Campos", "2B-2026", False),
    ("C26-001", "Sofía", "Jiménez Cruz", "3C-2026", True),
    ("C26-002", "Sebastián", "Ortega Paredes", "3C-2026", True),
    ("C26-003", "Regina", "Silva Montes", "3C-2026", True),
    ("C26-004", "Daniel", "Rojas Fuentes", "3C-2026", True),
    ("C25-001", "Andrea", "Pineda León", "3C-2025", False),
)

VARK = {
    "titulo": "Estilos de aprendizaje VARK",
    "descripcion": "Identifica cómo prefieres recibir y procesar información: visual, auditiva, "
                   "lectura/escritura o kinestésica. Ejemplo ficticio con fines de demostración.",
    "instrucciones": "Lee cada situación y marca todas las opciones que describan lo que harías. "
                     "Puedes elegir más de una.",
    "preguntas": (
        ("Necesitas llegar a un lugar que no conoces. ¿Qué prefieres?",
         ("Ver un mapa", "Que alguien me explique el camino", "Leer las indicaciones escritas", "Ir y orientarme sobre la marcha")),
        ("Vas a aprender a usar una aplicación nueva.",
         ("Ver capturas o diagramas", "Escuchar a alguien que ya la usa", "Leer el manual", "Probarla directamente")),
        ("Estás estudiando para un examen.",
         ("Hago esquemas y mapas mentales", "Repaso en voz alta o en grupo", "Releo y resumo mis apuntes", "Resuelvo ejercicios prácticos")),
        ("Quieres recordar una receta de cocina.",
         ("Miro fotos de cada paso", "Escucho a quien la prepara", "La escribo en una libreta", "La preparo varias veces")),
        ("Un docente explica un tema difícil.",
         ("Me ayuda que use gráficas", "Me ayuda que lo explique con ejemplos hablados", "Me ayuda tener lecturas", "Me ayuda una actividad práctica")),
        ("Eliges un regalo para alguien.",
         ("Me fijo en cómo se ve", "Pido opiniones", "Leo reseñas", "Lo pruebo en la tienda")),
        ("Debes presentar un proyecto.",
         ("Preparo diapositivas con imágenes", "Ensayo hablando", "Escribo un guion detallado", "Llevo una demostración")),
        ("Quieres mejorar en un deporte.",
         ("Veo videos de técnica", "Escucho consejos del entrenador", "Leo sobre estrategias", "Practico una y otra vez")),
    ),
}

PERSONALIDAD = {
    "titulo": "Preferencias de personalidad",
    "descripcion": "Explora tus preferencias en cuatro ejes (energía, información, decisiones y estilo de vida). "
                   "Ejemplo ficticio y orientativo; no es un instrumento clínico.",
    "instrucciones": "Reparte 10 puntos entre las dos opciones de cada pregunta según cuánto te describen. "
                     "No se permite el reparto 5 y 5.",
    "preguntas": (
        ("E", "I", "Después de una semana intensa recargas energía…", "Saliendo con amigos", "Con tiempo a solas"),
        ("E", "I", "En una reunión nueva sueles…", "Iniciar conversaciones", "Escuchar primero"),
        ("S", "N", "Al aprender algo nuevo prefieres…", "Datos y ejemplos concretos", "La idea general y sus posibilidades"),
        ("S", "N", "Te describirías como alguien…", "Práctico y realista", "Imaginativo y creativo"),
        ("T", "F", "Al tomar una decisión importante pesa más…", "El análisis lógico", "Cómo afecta a las personas"),
        ("T", "F", "Ante un desacuerdo prefieres…", "Ser directo y objetivo", "Cuidar la relación"),
        ("J", "P", "Para un viaje prefieres…", "Tener todo planeado", "Decidir sobre la marcha"),
        ("J", "P", "Con las tareas sueles…", "Terminarlas con anticipación", "Trabajar mejor cerca de la fecha límite"),
    ),
}

PUNTOS = (0, 1, 2, 3, 4, 6, 7, 8, 9, 10)


class Command(BaseCommand):
    help = "Carga datos ficticios en todas las secciones (grupos, estudiantes, cuestionarios, evaluaciones y resultados)."

    @transaction.atomic
    def handle(self, *args, **options):
        azar = random.Random(2026)  # Siempre los mismos datos.
        conteo = {"grupos": 0, "estudiantes": 0, "cuestionarios": 0, "evaluaciones": 0}

        grupos = {}
        for clave, nombre, activo in GRUPOS:
            grupos[clave], creado = Grupo.objects.get_or_create(clave=clave, defaults={"nombre": nombre, "activo": activo})
            conteo["grupos"] += creado

        estudiantes = []
        for matricula, nombres, apellidos, grupo, activo in ESTUDIANTES:
            correo = f"{nombres.lower()}.{apellidos.split()[0].lower()}@escuela.example".translate(
                str.maketrans("áéíóúñ", "aeioun")
            )
            estudiante, creado = Estudiante.objects.get_or_create(
                matricula=matricula,
                defaults={"nombres": nombres, "apellidos": apellidos, "correo": correo,
                          "grupo": grupos[grupo], "activo": activo},
            )
            conteo["estudiantes"] += creado
            estudiantes.append(estudiante)

        cuenta = get_user_model().objects.filter(username="demo.estudiante").first()
        if cuenta and not Estudiante.objects.filter(usuario=cuenta).exists():
            primero = estudiantes[0]
            if primero.usuario_id is None:
                primero.usuario = cuenta
                primero.save(update_fields=["usuario"])

        vark, creado = self.cuestionario_vark()
        conteo["cuestionarios"] += creado
        personalidad, creado = self.cuestionario_personalidad()
        conteo["cuestionarios"] += creado
        # Uno inactivo para ver el filtro de estado.
        _, creado = Cuestionario.objects.get_or_create(
            titulo="VARK (versión anterior)",
            defaults={"tipo": "VARK", "activo": False,
                      "descripcion": "Versión archivada del cuestionario VARK.",
                      "instrucciones": "Ya no se aplica; se conserva como referencia."},
        )
        conteo["cuestionarios"] += creado

        activos = [e for e in estudiantes if e.activo]
        for indice, estudiante in enumerate(activos):
            # Casi todos tienen VARK terminado; dos quedan en curso.
            if not Evaluacion.objects.filter(estudiante=estudiante, cuestionario=vark).exists():
                if indice in (3, 8):
                    self.vark_en_curso(estudiante, vark, azar)
                else:
                    self.vark_completo(estudiante, vark, azar)
                conteo["evaluaciones"] += 1
            # Dos de cada tres tienen personalidad terminada.
            if indice % 3 != 2 and not Evaluacion.objects.filter(estudiante=estudiante, cuestionario=personalidad).exists():
                self.personalidad_completa(estudiante, personalidad, azar)
                conteo["evaluaciones"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Datos de ejemplo cargados: "
            f"{conteo['grupos']} grupos, {conteo['estudiantes']} estudiantes, "
            f"{conteo['cuestionarios']} cuestionarios y {conteo['evaluaciones']} evaluaciones nuevas."
        ))
        self.stdout.write(
            f"Totales: {Grupo.objects.count()} grupos, {Estudiante.objects.count()} estudiantes, "
            f"{Cuestionario.objects.count()} cuestionarios, {Evaluacion.objects.count()} evaluaciones."
        )

    # --- Cuestionarios ---------------------------------------------------------

    def cuestionario_vark(self):
        cuestionario, creado = Cuestionario.objects.get_or_create(
            titulo=VARK["titulo"],
            defaults={"tipo": "VARK", "descripcion": VARK["descripcion"], "instrucciones": VARK["instrucciones"]},
        )
        if creado:
            for orden, (texto, opciones) in enumerate(VARK["preguntas"], start=1):
                pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto=texto, orden=orden)
                for posicion, (dimension, opcion) in enumerate(zip("VARK", opciones), start=1):
                    Opcion.objects.create(pregunta=pregunta, texto=opcion, dimension=dimension, orden=posicion)
        return cuestionario, creado

    def cuestionario_personalidad(self):
        cuestionario, creado = Cuestionario.objects.get_or_create(
            titulo=PERSONALIDAD["titulo"],
            defaults={"tipo": "PERSONALIDAD", "descripcion": PERSONALIDAD["descripcion"],
                      "instrucciones": PERSONALIDAD["instrucciones"]},
        )
        if creado:
            for orden, (uno, dos, texto, texto_uno, texto_dos) in enumerate(PERSONALIDAD["preguntas"], start=1):
                pregunta = Pregunta.objects.create(cuestionario=cuestionario, texto=texto, orden=orden)
                Opcion.objects.create(pregunta=pregunta, texto=texto_uno, dimension=uno, orden=1)
                Opcion.objects.create(pregunta=pregunta, texto=texto_dos, dimension=dos, orden=2)
        return cuestionario, creado

    # --- Evaluaciones ----------------------------------------------------------

    def responder_vark(self, evaluacion, preguntas, azar):
        preferida = azar.choice("VARK")
        for pregunta in preguntas:
            opciones = list(pregunta.opciones.all())
            elegidas = [o.pk for o in opciones if o.dimension == preferida or azar.random() < 0.3]
            guardar_respuesta(evaluacion.pk, pregunta.pk, elegidas or [azar.choice(opciones).pk])

    def vark_completo(self, estudiante, cuestionario, azar):
        evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
        self.responder_vark(evaluacion, cuestionario.preguntas.order_by("orden"), azar)
        finalizar_evaluacion(evaluacion.pk)

    def vark_en_curso(self, estudiante, cuestionario, azar):
        evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
        self.responder_vark(evaluacion, cuestionario.preguntas.order_by("orden")[:3], azar)

    def personalidad_completa(self, estudiante, cuestionario, azar):
        evaluacion = Evaluacion.objects.create(estudiante=estudiante, cuestionario=cuestionario)
        for pregunta in cuestionario.preguntas.order_by("orden"):
            uno, dos = pregunta.opciones.order_by("orden")
            puntos = azar.choice(PUNTOS)
            guardar_respuesta_personalidad(evaluacion.pk, pregunta.pk, uno.pk, puntos, dos.pk, 10 - puntos)
        finalizar_evaluacion(evaluacion.pk)
