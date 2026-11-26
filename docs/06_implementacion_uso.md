6. Implementación y uso del sistema
6.1 Requisitos previos
- Python 3.10+ (probado con 3.13).
- PostgreSQL 18 (o superior) con pgAdmin 4.
- Git.
- PowerShell (Windows) o terminal equivalente.

6.2 Instalación local
# 1. Clonar el repositorio
git clone <url-del-repo> vark-personalidad
Set-Location vark-personalidad
# 2. Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# 3. Instalar dependencias
pip install -r requirements.txt

6.3 Configuración de base de datos
- Crear base y usuario en PostgreSQL:
CREATE DATABASE vark_personalidad_db;
CREATE USER vark_app WITH PASSWORD 'una_clave_segura';
GRANT ALL PRIVILEGES ON DATABASE vark_personalidad_db TO vark_app;
\c vark_personalidad_db
GRANT USAGE, CREATE ON SCHEMA public TO vark_app;

- Crear .env a partir de .env.example y completar:
DJANGO_SECRET_KEY=una_clave_local_larga_y_aleatoria
DB_NAME=vark_personalidad_db
DB_USER=vark_app
DB_PASSWORD=una_clave_segura
DB_HOST=127.0.0.1
DB_PORT=5432
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=no-reply@vark.local
CONTACT_EMAIL=contacto@vark.local

- Verificar que .env está ignorado:
git check-ignore .env

6.4. Migraciones y datos DEMO

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py cargar_demo
python manage.py createsuperuser

6.5. Ejecución

python manage.py runserver
- Panel admin: http://127.0.0.1:8000/admin/
- Página principal: http://127.0.0.1:8000/
- API: http://127.0.0.1:8000/api/

6.6. Uso del panel administrativo
- Iniciar sesión con el superusuario.
- Administración → Roles de acceso: crear roles, asignar permisos y (opcionalmente) asignar a un usuario.
- Administración → Estudiantes / Grupos: crear grupos y estudiantes (o usar cargar_demo).
- Administración → Cuestionarios: crear cuestionarios con preguntas y opciones (inlines).
- Administración → Evaluaciones: iniciar evaluaciones y consultar su estado.
- Administración → Resultados: consultar resultados y puntajes; descargar PDF.
- Administración → Opciones seleccionadas: auditar respuestas.

6.7 Uso de la API

6.7.1 Autenticación
# Login
curl -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/login/ `
  -H "Content-Type: application/json" `
  -d '{"username":"admin","password":"clave"}'
# Me
curl -b cookies.txt http://127.0.0.1:8000/api/auth/me/
# Logout
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/auth/logout/
6.7.2. Flujo típico de evaluación
powershell
# 1. Iniciar evaluación
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/evaluaciones/iniciar/ `
  -H "Content-Type: application/json" `
  -d '{"estudiante":1,"cuestionario":1}'
# 2. Responder (VARK)
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/evaluaciones/1/responder/ `
  -H "Content-Type: application/json" `
  -d '{"respuestas":[{"pregunta":1,"opciones":[1,2]}],"calcular":false}'
# 3. Calcular y finalizar
curl -b cookies.txt -X POST http://127.0.0.1:8000/api/evaluaciones/1/calcular/ `
  -H "Content-Type: application/json" -d '{}'
# 4. Consultar resultado
curl http://127.0.0.1:8000/api/resultados/1/

6.7.3 Agregados y PDF

curl "http://127.0.0.1:8000/api/resultados/agregados/?alcance=total&tipo=VARK"
curl -o ficha.pdf "http://127.0.0.1:8000/api/resultados/1/pdf/"
curl -o fichas.pdf "http://127.0.0.1:8000/api/resultados/pdf/?alcance=total&tipo=VARK"

6.7.4 Búsqueda y contacto

curl "http://127.0.0.1:8000/api/buscar/?q=DEMO"
curl -X POST http://127.0.0.1:8000/api/contacto/ `
  -H "Content-Type: application/json" `
  -d '{"nombre":"Ana","correo":"ana@example.com","asunto":"Hola","mensaje":"Mensaje de prueba."}'

6.8 Uso del frontend
La página principal (/) ofrece:
- Formulario de configuración de evaluación (#assessmentSetup): selección de estudiante y cuestionario, botones VARK/Personalidad.
- Acceso al panel (/admin/login/?next=/).
- Constructor visual de cuestionarios en Administración → Cuestionarios → Agregar (solo vista previa, no persiste).

6.9 Pruebas de interfaz
Las pruebas del panel comprueban páginas renderizadas, enlaces y permisos visibles; no ejecutan JavaScript. Para pruebas reales de navegador se recomienda Selenium o Playwright (no incluidas).

6.10. Despliegue local (resumen)
+-----------------------------------------------------+
| 1. PostgreSQL en 127.0.0.1:5432                     |
| 2. .env configurado                                 |
| 3. python manage.py migrate                         |
| 4. python manage.py cargar_demo (opcional)          |
| 5. python manage.py runserver                       |
| 6. Acceso a /admin/, / y /api/                      |
+-----------------------------------------------------+