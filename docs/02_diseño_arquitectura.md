# 2. Diseño y arquitectura
## 2.1. Visión general

El sistema sigue una **arquitectura web en tres capas** con un **monolito modular** en Django:

+----------------------------------------------------------+
|  Capa de presentación                                    |
|  - Sitio público "Brújula" (templates/dashboard)         |
|  - Panel administrativo personalizado (templates/admin)  |
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

## 2.2. Decisiones arquitectónicas y alternativas descartadas

| Decisión | Alternativa considerada | Razón |
|---|---|---|
|Monolito modular Django | Microservicios	| Menos infraestructura y complejidad para el plazo.|
|PostgreSQL 18 | SQLite | Mejor manejo relacional, permisos y DER desde pgAdmin.|
|Django ORM + migraciones	| SQL manual | Esquema versionado y reproducible.|
|vark_app (usuario BD) | postgres	| Menor exposición de privilegios.|
|.env + python-dotenv	| Credenciales en settings.py	| Evitar publicar secretos.|
|Selecciones como entidad	| opcion_id único en Respuesta | Permitir múltiples selecciones VARK.|
|Resultado separado de Evaluacion |	Puntajes en cada respuesta | Separar origen, cálculo e interpretación.|
|Fachada ScoringService (Singleton)	| Lógica en la vista	| Único punto de entrada al cálculo.|
|Permisos por sesión (sin DRF)	| Django REST Framework	| Simplicidad; el equipo no requería DRF.|
|PDF con reportlab platypus	| WeasyPrint / wkhtmltopdf	| Sin dependencias nativas.|
|Personalización total del admin	| Usar admin por defecto	| Identidad visual "Brújula" y mejor UX.|
|JS sin framework	| React/Vue	| El alcance no requiere SPA; se mantiene ligero.|

## 2.3. Estructura modular del proyecto

vark-personalidad/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── templates/
│   ├── dashboard/
│   │   └── index.html          (sitio público Brújula)
│   └── admin/
│       ├── base_site.html      (branding del panel)
│       ├── app_list.html       (secciones del panel)
│       ├── index.html          (dashboard con tablero)
│       ├── login.html          (login personalizado)
│       ├── filter.html         (filtros compactos)
│       ├── popup_response.html (modales de registros relacionados)
│       ├── change_form.html    (constructor visual / roles)
│       ├── change_list.html    (roles / evaluaciones / opciones)
│       └── brujuela_results_dashboard.html
├── static/
│   ├── dashboard/
│   │   ├── styles.css          (sitio público)
│   │   └── app.js              (navegación y formulario de evaluación)
│   └── admin/
│       ├── css/
│       │   ├── brujuela-admin.css
│       │   └── brujuela-login.css
│       └── js/
│           ├── brujuela-admin.js
│           ├── brujuela-ejemplos.js
│           ├── brujuela-evaluacion.js
│           └── brujuela-questionnaire-builder.js
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

## 2.4. Flujo de una evaluación

Admin                API                    Servicios               BD
  |                   |                        |                    |
  |-- POST iniciar -->|                        |                    |
  |                   |-- create Evaluacion -->|------------------->|
  |<-- 201/200 -------|                        |                    |
  |                   |                        |                    |
  |-- POST responder->|                        |                    |
  |                   |-- guardar_respuesta -->|------------------->|
  |                   |   (valida opciones)    |                    |
  |<-- 200 -----------|                        |                    |
  |                   |                        |                    |
  |-- POST calcular ->|                        |                    |
  |                   |-- ScoringService ----->|                    |
  |                   |   .calculate()         |-- finalizar_eval-->|
  |                   |                        |   (valida, calcula,|
  |                   |                        |    guarda, cierra) |
  |<-- 200 + payload -|                        |                    |

## 2.5. Diagrama de componentes

+-------------------+       +--------------------+       +---------------------+
|  apps.dashboard   |       |     apps.api       |       | apps.questionnaires |
|  (admin, home)    |<----->|  (views, urls)     |<----->| (Cuestionario,      |
+-------------------+       +---------+----------+       |  Pregunta, Opcion)  |
                                    |                    +---------------------+
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

## 2.6. Diagrama de despliegue (local)

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

## 2.7. Middleware y seguridad

- SecurityMiddleware, SessionMiddleware, CsrfViewMiddleware, AuthenticationMiddleware, MessageMiddleware.
- AdminPopupXFrameOptionsMiddleware: relaja X-Frame-Options a SAMEORIGIN en /admin/ cuando _popup=1 o en /admin/login/, para permitir popups del admin.
- @method_decorator(csrf_exempt, name="dispatch") en las vistas de la API (autenticación por sesión, no por token CSRF). La protección real se complementa con:
-- @require_staff en escrituras (POST/PUT/PATCH/DELETE).
-- Validación de origen por sesión (cookies sessionid + csrftoken).
- @require_staff devuelve 401 si no hay sesión y 403 si el usuario no es staff.

## 2.8. Capa de presentación: frontend
El frontend se compone de dos bloques:

### 2.8.1. Sitio público "Brújula" (templates/dashboard/index.html)

- Navegación por secciones: Inicio, Instrumentos, Guía de uso.
- Barra lateral con marca, enlaces y tarjeta de ayuda.
- Hero con copy "Aprende a tu manera".
- Tarjetas de instrumentos VARK y Personalidad.
- Formulario de configuración de evaluación (#assessmentSetup).
- Estilos en static/dashboard/styles.css; lógica en static/dashboard/app.js.

### 2.8.2. Panel administrativo personalizado (templates/admin/)

- base_site.html: branding "b. brújula. ADMINISTRACIÓN", CSS/JS propios.
- index.html: dashboard con tablero, secciones y actividad reciente.
- login.html: pantalla dividida con panel verde y tarjeta de login.
- app_list.html: renombra secciones y agrega descripciones.
- filter.html: filtros compactos en <details>.
- change_form.html: constructor visual de cuestionarios y plantillas de roles.
- change_list.html: roles, evaluaciones de prueba y opciones seleccionadas.
- brujuela_results_dashboard.html: tablero con estadísticas y gráfico VARK.

### 2.8.3. Estilos y scripts

- brujuela-admin.css y brujuela-login.css: rediseño del admin.
- brujuela-admin.js: mejora UX del admin.
- brujuela-ejemplos.js: datos ficticios.
- brujuela-evaluacion.js: evaluación de prueba (no persiste).
- brujuela-questionnaire-builder.js: constructor visual (no persiste).