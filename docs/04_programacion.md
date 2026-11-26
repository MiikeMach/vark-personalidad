# 4. Programación
## 4.1. Mapa de módulos

| Módulo | Responsabilidad | Archivos clave |
|---|---|---|
| `apps.accounts` | Reservado para funciones de cuentas (vacío en esta versión; se usa `auth.User`). | `apps.py` |
| `apps.api` | Endpoints REST, serializadores manuales, agregados, PDF, contacto. | `views.py`, `urls.py`, `serializers.py`, `aggregations.py`, `pdf.py`, `auth.py` |
| `apps.assessments` | Evaluaciones, respuestas y servicios de guardado. | `models.py`, `services.py` |
| `apps.contact` | Esqueleto; la lógica de contacto está en `api`. | `apps.py` |
| `apps.dashboard` | Panel administrativo personalizado, roles, usuarios, home, templates y JS del admin. | `admin.py`, `admin_actions.py`, `middleware.py`, `views.py`, `templates/admin/*`, `static/admin/*` |
| `apps.questionnaires` | Cuestionarios, preguntas y opciones. | `models.py`, `admin.py` |
| `apps.reports` | Esqueleto; la generación de PDF está en `api`. | `apps.py` |
| `apps.results` | Resultados persistidos y servicios de finalización. | `models.py`, `services.py` |
| `apps.scoring` | Cálculo de puntajes VARK y personalidad, fachada Singleton. | `services.py`, `service.py` |
| `apps.students` | Grupos y estudiantes; comando `cargar_demo`. | `models.py`, `management/commands/cargar_demo.py` |

## 4.2. Modelos de datos

- `students`: `Grupo`, `Estudiante`.
- `questionnaires`: `Cuestionario`, `Pregunta`, `Opcion`.
- `assessments`: `Evaluacion`, `Respuesta`, `SeleccionRespuesta`.
- `results`: `Resultado`, `PuntajeDimension`.

## 4.3. Servicios de negocio

### 4.3.1. `apps.assessments.services`

- `validar_selecciones(evaluacion, pregunta_id, opcion_ids)`: verifica tipos, duplicados, pertenencia a la pregunta y al cuestionario, y restricción de una sola opción en personalidad.
- `validar_evaluacion_editable(evaluacion)`: rechaza modificaciones si el estado no es `EN_PROGRESO`.
- `guardar_respuesta(evaluacion_id, pregunta_id, opcion_ids)`: guarda o reemplaza selecciones VARK (permite lista vacía para omisión).
- `validar_distribucion_personalidad(p1, p2)`: exige enteros entre 0 y 10, suma 10 y prohíbe 5/5.
- `validar_par_personalidad(d1, d2)`: exige un par de dimensiones opuestas.
- `guardar_respuesta_personalidad(...)`: guarda o reemplaza la distribución de puntos.

### 4.3.2. `apps.results.services`

- `validar_respuestas_para_finalizar(evaluacion)`: comprueba integridad (pertenencia, dimensiones válidas, ausencia de `puntos` en VARK, distribución válida en personalidad y, en personalidad, que **todas** las preguntas estén contestadas).
- `guardar_resultado(evaluacion_id)`: calcula puntajes, cuenta contestadas/omitidas, crea/actualiza `Resultado` y sus `PuntajeDimension`, y elimina dimensiones sobrantes.
- `finalizar_evaluacion(evaluacion_id)`: valida, guarda resultado y cambia el estado a `FINALIZADA` dentro de una transacción.

### 4.3.3. `apps.scoring`

- `calcular_puntajes_vark(evaluacion)`: cuenta selecciones por dimensión (V/A/R/K).
- `calcular_puntajes_personalidad(evaluacion)`: suma `puntos` por dimensión (E/I/S/N/T/F/J/P).
- `generar_perfil_personalidad(puntajes)`: devuelve una cadena de 4 letras o `None` si hay empate o faltan datos.
- `ScoringService` (Singleton): fachada con `calculate(evaluacion, interpretacion="")` que delega en `finalizar_evaluacion` y rechaza interpretación manual.

## 4.4. API REST

- Implementada con `View` de Django y `JsonResponse`.
- Autenticación por sesión (`login`, `logout`, `me`).
- Permisos:
  - `@require_staff` en `responder`, `calcular` y escrituras CRUD.
  - `@method_decorator(csrf_exempt, name="dispatch")` en todas las vistas de la API para evitar el bloqueo CSRF en peticiones AJAX desde el frontend (la sesión y `require_staff` siguen protegiendo las escrituras).
- Serializadores manuales (`serializers.py`): funciones `*_to_dict`.
- Endpoints principales (ver Anexo A).

### 4.4.1. Ejemplo de petición autenticada

# Login y guardado de cookies
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"clave"}'

# Petición autenticada con la cookie de sesión
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/evaluaciones/iniciar/ \
  -H "Content-Type: application/json" \
  -d '{"estudiante":1,"cuestionario":1}'

## 4.5. Reglas de negocio codificadas

| Regla | Implementación |
|---|---|
| Matrícula única | UNIQUE en modelo y validación en API.|
| No borrar grupo con estudiantes | on_delete=PROTECT.|
| No duplicar orden de preguntas/opciones | UNIQUE(cuestionario, orden), UNIQUE(pregunta, orden).|
| VARK permite varias selecciones | validar_selecciones + selecciones como entidad.|
| VARK permite omitir | Lista vacía en guardar_respuesta.|
| Personalidad exige 2 opciones opuestas | validar_par_personalidad.|
| Personalidad exige 10 puntos sin 5/5 | validar_distribucion_personalidad.|
| No modificar evaluación finalizada | validar_evaluacion_editable y finalizar_evaluacion.|
| Un resultado por evaluación | OneToOneField en Resultado.|
| Puntajes no negativos | PositiveIntegerField + validaciones.|

## 4.6. Generación de PDF

apps.api.pdf usa reportlab.platypus:
- construir_pdf_individual(resultado) → ficha de un resultado.
- construir_pdf_multiple(qs, alcance, tipo) → portada agregada + fichas individuales.

## 4.7. Contacto

ContactoView valida campos (nombre, correo, asunto, mensaje), construye el cuerpo y usa django.core.mail.send_mail. En desarrollo usa console.EmailBackend.

## 4.8. Comando cargar_demo

Crea/actualiza:
- Grupo DEMO-01.
- Estudiantes DEMO-001..003.
- Dos cuestionarios (DEMO - Estilos de aprendizaje VARK, DEMO - Preferencias de personalidad) con preguntas y opciones.

## 4.9. Frontend: lógica y scripts
### 4.9.1. Sitio público (static/dashboard/app.js)

- Navegación por secciones (data-route).
- Carga de estudiantes y cuestionarios desde la API.
- Envío del formulario de inicio de evaluación (#assessmentSetup).
- Renderizado de preguntas y envío de respuestas.

### 4.9.2. Panel administrativo (static/admin/js/)

- brujuela-admin.js:
-- Traduce nombres de permisos a lenguaje natural.
-- Añade buscador de usuarios en el formulario de roles.
-- Implementa modales para agregar/editar/eliminar registros relacionados sin salir de la página.
-- Menú móvil para la barra lateral.
-- Cierre de filtros al hacer clic fuera.
- brujuela-ejemplos.js: datos ficticios de cuestionarios VARK y personalidad.
- brujuela-evaluacion.js:
-- Carga ejemplos o JSON compatible.
-- Valida estructura del cuestionario.
-- Renderiza preguntas (checkbox para VARK, radio para personalidad).
-- Calcula perfil orientativo y muestra advertencia de que no se guarda.
- brujuela-questionnaire-builder.js:
-- Construye un cuestionario desde cero (título, tipo, descripción, instrucciones, preguntas y opciones).
-- Valida dimensiones según el tipo.
-- Muestra vista previa en el navegador.
-- No persiste en la base de datos.