
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.students.models import Grupo, Estudiante
from apps.questionnaires.models import Cuestionario, Pregunta, Opcion


class Command(BaseCommand):
    help = "Carga datos ficticios de demostración para VARK-Personalidad."

    @transaction.atomic
    def handle(self, *args, **options):
        grupo, _ = Grupo.objects.update_or_create(
            clave="DEMO-01",
            defaults={
                "nombre": "Grupo de demostración",
                "activo": True,
            },
        )

        estudiantes = [
            ("DEMO-001", "Ana", "Ejemplo"),
            ("DEMO-002", "Carlos", "Prueba"),
            ("DEMO-003", "Lucía", "Demostración"),
        ]

        for matricula, nombres, apellidos in estudiantes:
            Estudiante.objects.update_or_create(
                matricula=matricula,
                defaults={
                    "nombres": nombres,
                    "apellidos": apellidos,
                    "grupo": grupo,
                    "activo": True,
                },
            )

        ejemplos = [
            {
                "titulo": "DEMO - Estilos de aprendizaje VARK",
                "tipo": Cuestionario.Tipo.VARK,
                "descripcion": (
                    "Cuestionario ficticio para demostrar el sistema. "
                    "No es un instrumento validado."
                ),
                "instrucciones": (
                    "Selecciona una o varias opciones por pregunta."
                ),
                "preguntas": [
                    (
                        "Cuando quiero aprender algo nuevo, prefiero:",
                        [
                            ("Observar un esquema", "V"),
                            ("Escuchar una explicación", "A"),
                            ("Leer instrucciones", "R"),
                            ("Practicar directamente", "K"),
                        ],
                    ),
                    (
                        "Para recordar información me ayuda:",
                        [
                            ("Ver imágenes", "V"),
                            ("Conversar sobre el tema", "A"),
                            ("Tomar notas", "R"),
                            ("Realizar ejercicios", "K"),
                        ],
                    ),
                    (
                        "Cuando recibo indicaciones prefiero:",
                        [
                            ("Un diagrama", "V"),
                            ("Que me expliquen verbalmente", "A"),
                            ("Un documento escrito", "R"),
                            ("Una demostración práctica", "K"),
                        ],
                    ),
                    (
                        "Al estudiar un tema nuevo suelo:",
                        [
                            ("Revisar gráficos", "V"),
                            ("Escuchar ejemplos", "A"),
                            ("Leer resúmenes", "R"),
                            ("Resolver actividades", "K"),
                        ],
                    ),
                ],
            },
            {
                "titulo": "DEMO - Preferencias de personalidad",
                "tipo": Cuestionario.Tipo.PERSONALIDAD,
                "descripcion": (
                    "Ejemplo académico ficticio de pares de preferencias. "
                    "No constituye una evaluación psicológica validada."
                ),
                "instrucciones": (
                    "Distribuye 10 puntos entre las dos opciones de "
                    "cada pregunta, sin utilizar 5 y 5."
                ),
                "preguntas": [
                    (
                        "En situaciones sociales tiendo a:",
                        [
                            ("Buscar interacción con otras personas", "E"),
                            ("Preferir espacios de reflexión individual", "I"),
                        ],
                    ),
                    (
                        "Cuando analizo información prefiero:",
                        [
                            ("Concentrarme en datos concretos", "S"),
                            ("Explorar posibilidades e ideas", "N"),
                        ],
                    ),
                    (
                        "Para tomar decisiones suelo valorar:",
                        [
                            ("Los criterios lógicos", "T"),
                            ("El impacto en las personas", "F"),
                        ],
                    ),
                    (
                        "Al organizar mis actividades prefiero:",
                        [
                            ("Seguir un plan definido", "J"),
                            ("Mantener opciones abiertas", "P"),
                        ],
                    ),
                ],
            },
        ]

        for ejemplo in ejemplos:
            cuestionario, _ = Cuestionario.objects.get_or_create(
                titulo=ejemplo["titulo"],
                tipo=ejemplo["tipo"],
                defaults={
                    "descripcion": ejemplo["descripcion"],
                    "instrucciones": ejemplo["instrucciones"],
                    "activo": True,
                },
            )

            for orden, (texto, opciones) in enumerate(
                ejemplo["preguntas"], start=1
            ):
                pregunta, _ = Pregunta.objects.get_or_create(
                    cuestionario=cuestionario,
                    orden=orden,
                    defaults={"texto": texto},
                )

                for orden_opcion, (texto_opcion, dimension) in enumerate(
                    opciones, start=1
                ):
                    Opcion.objects.get_or_create(
                        pregunta=pregunta,
                        orden=orden_opcion,
                        defaults={
                            "texto": texto_opcion,
                            "dimension": dimension,
                        },
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "Datos DEMO preparados correctamente: "
                "1 grupo, 3 estudiantes y 2 cuestionarios."
            )
        )
