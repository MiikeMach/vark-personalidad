# Anexo A. Referencia de la API

Base: `http://127.0.0.1:8000/api/`

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `auth/login/` | — | Inicia sesión. |
| POST | `auth/logout/` | Sesión | Cierra sesión. |
| GET | `auth/me/` | Sesión | Devuelve el usuario actual o 401. |
| GET/POST | `grupos/` | GET público / POST staff | Lista o crea grupos. |
| GET/PUT/PATCH/DELETE | `grupos/<pk>/` | Lectura pública / escritura staff | Detalle de grupo. |
| GET/POST | `estudiantes/` | GET público / POST staff | Lista o crea estudiantes. |
| GET/PUT/PATCH/DELETE | `estudiantes/<pk>/` | Lectura pública / escritura staff | Detalle de estudiante. |
| GET/POST | `cuestionarios/` | GET público / POST staff | Lista o crea cuestionarios. |
| GET/PUT/PATCH/DELETE | `cuestionarios/<pk>/` | Lectura pública / escritura staff | Detalle. |
| GET | `cuestionarios/<pk>/completo/` | Público | Cuestionario con preguntas y opciones. |
| GET/POST | `preguntas/`, `opciones/` | Igual que arriba | CRUD. |
| GET/POST | `evaluaciones/` | GET público / POST staff | Lista o crea evaluaciones. |
| POST | `evaluaciones/iniciar/` | Sesión | Inicia o reutiliza evaluación. |
| GET/PUT/PATCH/DELETE | `evaluaciones/<pk>/` | Lectura pública / escritura staff | Detalle. |
| POST | `evaluaciones/<pk>/responder/` | Staff | Guarda respuestas en bloque. |
| POST | `evaluaciones/<pk>/calcular/` | Staff | Calcula y finaliza. |
| GET | `buscar/?q=` | Público | Busca estudiantes y grupos. |
| GET | `resultados/` | Público | Lista resultados con filtros. |
| GET | `resultados/agregados/` | Público | Agregados por alcance/tipo. |
| GET | `resultados/pdf/` | Público | PDF múltiple. |
| GET | `resultados/<pk>/pdf/` | Público | PDF individual. |
| GET | `resultados/<pk>/` | Público | Detalle. |
| GET | `dashboard/grupal/` | Público | Alias de agregados/grupal. |
| GET | `puntajes/`, `puntajes/<pk>/` | Público | Puntajes por dimensión. |
| POST | `contacto/` | Público | Envía correo de contacto. |