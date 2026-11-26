# 1. Análisis de requerimientos
## 1.1. Propósito del sistema

El sistema **VARK-Personalidad** (marca pública **Brújula**) es una plataforma web académica para la aplicación, evaluación y análisis de dos instrumentos:
- **VARK**: cuestionario de preferencias de aprendizaje declaradas (Visual, Auditivo, Lectura/Escritura, Kinestésico).
- **Personalidad**: cuestionario de preferencias basado en las dimensiones de Jung y Myers-Briggs (E/I, S/N, T/F, J/P).

El sistema permite administrar grupos y estudiantes, presentar cuestionarios, registrar intentos y respuestas, calcular puntuaciones por dimensión, almacenar resultados y generar reportes PDF. Se enfatiza que **VARK no evalúa conocimientos** y que el instrumento de personalidad **no constituye un diagnóstico psicológico**, sino una clasificación descriptiva.

La interfaz se divide en dos experiencias:
- **Sitio público "Brújula"** (`apps.dashboard` + `templates/dashboard/index.html`): presentación de los instrumentos, guía de uso, formulario de inicio de evaluación y acceso al panel administrativo.
- **Panel de gestión "Brújula Administración"** (`templates/admin/` personalizados): dashboard con tablero de resultados, gestión de estudiantes, cuestionarios, evaluaciones, resultados, roles y usuarios.

## 1.2. Actores del sistema

| Actor | Descripción | Permisos principales |
|---|---|---|
| **Administrador** | Usuario con `is_staff=True` o `is_superuser=True`. | Gestión completa vía panel de Django y API administrativa. |
| **Usuario autenticado (no staff)** | Usuario con sesión activa pero sin privilegios de administrador. | Consulta de catálogos y uso de endpoints de solo lectura. |
| **Visitante** | Sin sesión. | Consulta pública de cuestionarios completos, búsqueda, agregados y PDFs. Navegación por el sitio público. |
| **Estudiante** | Entidad académica (no es un usuario del sistema en esta versión). | Sus datos y evaluaciones son gestionados por el administrador. |

## 1.3. Requerimientos funcionales

| ID | Requerimiento | Módulo | Estado |
|---|---|---|---|
| RF-01 | Autenticación por sesión (login/logout/me). | `api` | Implementado |
| RF-02 | Gestión de grupos (CRUD). | `students` | Implementado |
| RF-03 | Gestión de estudiantes (CRUD). | `students` | Implementado |
| RF-04 | Gestión de cuestionarios, preguntas y opciones (CRUD). | `questionnaires` | Implementado |
| RF-05 | Inicio de evaluación (idempotente). | `assessments` | Implementado |
| RF-06 | Registro de respuestas VARK (múltiples opciones, omisiones). | `assessments` | Implementado |
| RF-07 | Registro de respuestas de personalidad (distribución de 10 puntos por par). | `assessments` | Implementado |
| RF-08 | Cálculo de puntajes por dimensión y finalización de evaluación. | `scoring` / `results` | Implementado |
| RF-09 | Interpretación automática de perfil de personalidad (4 letras). | `scoring` | Implementado |
| RF-10 | Consulta de resultados individuales y agregados (individual/grupal/total). | `api` | Implementado |
| RF-11 | Generación de PDF individual y múltiple. | `api` | Implementado |
| RF-12 | Búsqueda de estudiantes y grupos. | `api` | Implementado |
| RF-13 | Formulario de contacto por correo. | `api` | Implementado |
| RF-14 | Panel administrativo con roles y permisos personalizados. | `dashboard` | Implementado |
| RF-15 | Carga de datos DEMO vía comando. | `students`/`questionnaires` | Implementado |
| RF-16 | Sitio público "Brújula" con navegación por secciones (Inicio, Instrumentos, Guía). | `dashboard` | Implementado |
| RF-17 | Tablero de resultados en el panel administrativo (estadísticas, gráfico VARK, últimas evaluaciones, búsqueda). | `dashboard` | Implementado |
| RF-18 | Constructor visual de cuestionarios (vista previa en navegador, no persiste). | `dashboard` | Implementado |
| RF-19 | Evaluación de prueba interactiva (responde y calcula perfil orientativo, no persiste). | `dashboard` | Implementado |
| RF-20 | Personalización completa del panel administrativo (branding, login, listas, filtros, modales). | `dashboard` | Implementado |

## 1.4. Requerimientos no funcionales

| ID | Requerimiento | Cumplimiento |
|---|---|---|
| RNF-01 | Seguridad de credenciales vía `.env`. | `python-dotenv`; `.env` fuera de Git. |
| RNF-02 | Base de datos relacional PostgreSQL. | `psycopg` 3.3.9; PostgreSQL 18. |
| RNF-03 | Validaciones en servidor (no solo cliente). | Servicios en `assessments`, `results`, `scoring`. |
| RNF-04 | Operaciones atómicas en escrituras críticas. | `transaction.atomic` en servicios. |
| RNF-05 | Respuestas JSON uniformes. | `JsonResponse` en `api/views.py`. |
| RNF-06 | Idioma español (código y mensajes). | `LANGUAGE_CODE = 'es-mx'`. |
| RNF-07 | Generación de PDF sin dependencias nativas. | `reportlab` (platypus). |
| RNF-08 | Reproducibilidad del esquema. | Migraciones Django versionadas. |
| RNF-09 | Trazabilidad de cambios. | Git + ramas `feature/*` + PRs. |
| RNF-10 | Interfaz responsiva (móvil, tableta, escritorio). | CSS con `@media` en `brujuela-admin.css` y `brujuela-login.css`. |
| RNF-11 | Accesibilidad (roles ARIA, foco visible, textos alternativos). | `aria-*`, `role`, `:focus-visible` en CSS y plantillas. |
| RNF-12 | Protección CSRF en la API de escritura. | `csrf_exempt` en vistas de API para sesión, con `require_staff` y validación de origen. |

## 1.5. Casos de uso principales
+-------------------+-------------------------------------------+
| Caso de uso       | Descripción breve                         |
+-------------------+-------------------------------------------+
| CU-01 Login       | El usuario inicia sesión por API.         |
| CU-02 Iniciar     | El admin inicia una evaluación para un    |
|       evaluación  | estudiante y un cuestionario.             |
| CU-03 Responder   | El admin envía respuestas (VARK o         |
|                   | personalidad) y opcionalmente calcula.    |
| CU-04 Calcular    | El admin finaliza la evaluación y guarda  |
|                   | resultados.                               |
| CU-05 Consultar   | Cualquier visitante consulta resultados   |
|       resultados  | individuales, grupales o totales.         |
| CU-06 Exportar    | Cualquier visitante descarga PDF de       |
|       PDF         | ficha individual o agregada.              |
| CU-07 Buscar      | Cualquier visitante busca estudiantes y   |
|                   | grupos por texto.                         |
| CU-08 Contacto    | Cualquier visitante envía un mensaje.     |
| CU-09 Explorar    | Cualquier visitante navega por el sitio   |
|       sitio       | público (Inicio, Instrumentos, Guía).     |
| CU-10 Constructor | El admin prepara un cuestionario en el    |
|       visual      | constructor (vista previa, no persiste).  |
+-------------------+-------------------------------------------+

## 1.6. Restricciones y supuestos
- Entrega académica cercana, trabajo paralelo de tres integrantes.
- Herramientas gratuitas (Django, PostgreSQL, reportlab).
- Un solo backend Django (monolito modular), no microservicios.
- El frontend consume la API por HTTP/JSON y se sirve desde apps.dashboard.
- En esta versión, el estudiante no es un usuario autenticable; las evaluaciones las inicia el administrador.
- El constructor visual y la evaluación de prueba no persisten en la base de datos; son herramientas de demostración en el navegador.