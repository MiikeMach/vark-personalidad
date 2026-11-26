2. Diseño y arquitectura
2.1 Visión general
El sistema sigue una arquitectura web en tres capas con un monolito modular en Django:
+----------------------------------------------------------+
|  Capa de presentación                                    |
|  - Plantillas Django (apps.dashboard)                    |
|  - HTML/CSS/JS (frontend del compañero)                  |
+---------------------------+------------------------------+
                            | HTTP / JSON
+---------------------------v------------------------------+
|  Capa de aplicación (Django)                             |
|  - apps.api         (endpoints)                          |
|  - apps.assessments (servicios de guardado)              |
|  - apps.results     (servicios de cálculo/cierre)        |
|  - apps.scoring     (cálculo de puntajes)                |
|  - apps.dashboard   (admin personalizado, middleware)    |
+---------------------------+------------------------------+
                            | Django ORM
+---------------------------v------------------------------+
|  Capa de persistencia                                    |
|  - PostgreSQL 18                                         |
|  - Tablas con FK, UNIQUE y CHECK vía migraciones         |
+----------------------------------------------------------+

2.2. Decisiones arquitectónicas y alternativas descartadas
Decisión	Alternativa considerada	Razón
Monolito modular Django	Microservicios	Menos infraestructura y complejidad para el plazo.
PostgreSQL 18	SQLite	Mejor manejo relacional, permisos y DER desde pgAdmin.
Django ORM + migraciones	SQL manual	Esquema versionado y reproducible.
vark_app (usuario BD)	postgres	Menor exposición de privilegios.
.env + python-dotenv	Credenciales en settings.py	Evitar publicar secretos.
Selecciones como entidad	opcion_id único en Respuesta	Permitir múltiples selecciones VARK.
Resultado separado de Evaluacion	Puntajes en cada respuesta	Separar origen, cálculo e interpretación.
Fachada ScoringService (Singleton)	Lógica en la vista	Único punto de entrada al cálculo.
Permisos por sesión (sin DRF)	Django REST Framework	Simplicidad; el equipo no requería DRF.
PDF con reportlab platypus	WeasyPrint / wkhtmltopdf	Sin dependencias nativas.

2.3. Estructura modular del proyecto
vark-personalidad/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── apps/
    ├── accounts/        (esqueleto)
    ├── api/             (endpoints, serializadores, PDF, agregados)
    ├── assessments/     (evaluaciones, respuestas, servicios)
    ├── contact/         (esqueleto; lógica en api)
    ├── dashboard/       (admin, middleware, home)
    ├── questionnaires/  (cuestionarios, preguntas, opciones)
    ├── reports/         (esqueleto; lógica en api)
    ├── results/         (resultados, servicios)
    ├── scoring/         (cálculo de puntajes, fachada)
    └── students/        (grupos, estudiantes)

2.4. Flujo de una evaluación
Admin                API                    Servicios              BD
  |                   |                        |                   |
  |-- POST iniciar -->|                        |                   |
  |                   |-- create Evaluacion -->|------------------>|
  |<-- 201/200 -------|                        |                   |
  |                   |                        |                   |
  |-- POST responder->|                        |                   |
  |                   |-- guardar_respuesta -->|------------------>|
  |                   |   (valida opciones)    |                   |
  |<-- 200 -----------|                        |                   |
  |                   |                        |                   |
  |-- POST calcular ->|                        |                   |
  |                   |-- ScoringService ----->|                   |
  |                   |   .calculate()         |-- finalizar_eval->|
  |                   |                        |   (valida, calcula,|
  |                   |                        |    guarda, cierra) |
  |<-- 200 + payload -|                        |                   |

2.5. Diagrama de componentes
+-------------------+       +--------------------+       +------------------+
|  apps.dashboard   |       |     apps.api       |       | apps.questionnaires |
|  (admin, home)    |<----->|  (views, urls)     |<----->| (Cuestionario,   |
+-------------------+       +---------+----------+       |  Pregunta, Opcion)|
                                    |                    +------------------+
                                    |
              +---------------------+---------------------+
              |                     |                     |
    +---------v---------+  +--------v--------+   +--------v--------+
    | apps.assessments  |  |  apps.results   |   |  apps.scoring   |
    | (servicios)       |  |  (servicios)    |   |  (cálculo)      |
    +---------+---------+  +--------+--------+   +--------+--------+
              |                     |                     |
              +----------+----------+----------+----------+
                         |                     |
                +--------v--------+   +--------v--------+
                | apps.students   |   | PostgreSQL      |
                +-----------------+   +-----------------+

2.6. Diagrama de despliegue (local)
+-------------------------------+         +---------------------------+
|  Máquina del desarrollador    |         |  PostgreSQL 18            |
|  (Windows / PowerShell)       |         |  (127.0.0.1:5432)         |
|                               |         |                           |
|  +-------------------------+  |  TCP    |  +---------------------+  |
|  | .venv (Python 3.x)      |  |<------->|  | vark_personalidad_db|  |
|  | Django 5.2.19           |  |         |  +---------------------+  |
|  | runserver 127.0.0.1:8000|  |         |                           |
|  +-------------------------+  |         +---------------------------+
+-------------------------------+

2.7. Middleware y seguridad
- SecurityMiddleware, SessionMiddleware, CsrfViewMiddleware, AuthenticationMiddleware, MessageMiddleware.
- AdminPopupXFrameOptionsMiddleware: relaja X-Frame-Options a SAMEORIGIN en /admin/ cuando _popup=1 o en /admin/login/, para permitir popups del admin.
- @method_decorator(csrf_exempt, name="dispatch") en las vistas de la API (autenticación por sesión, no por token CSRF).
- @require_staff protege escrituras (POST/PUT/PATCH/DELETE).