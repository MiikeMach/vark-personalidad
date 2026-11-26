Anexo B. Comandos útiles

# Entorno
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Django
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py showmigrations
python manage.py sqlmigrate assessments 0001
python manage.py createsuperuser
python manage.py cargar_demo
python manage.py runserver

# Pruebas
python manage.py test apps --verbosity 1
python manage.py test apps.api --verbosity 2
python manage.py test apps.assessments.tests.ValidarSeleccionesTests

# Git
git check-ignore .env
git status
git log --oneline --graph --all