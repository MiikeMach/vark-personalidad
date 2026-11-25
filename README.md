# vark-personalidad
Plataforma web académica para la aplicación, evaluación y análisis de los instrumentos VARK y de personalidad basados en Jung y Myers-Briggs.

## Roles de acceso

En Administración → Roles de acceso, selecciona una plantilla y revisa sus permisos antes de guardar. Opcionalmente puedes asignar el rol a un usuario existente; esto no elimina sus otros roles ni permisos. Al editar un rol, sus permisos se conservan salvo que elijas otra plantilla y guardes. La lista de roles permite ver sus usuarios.

Los permisos del rol no son necesariamente todos los permisos de una cuenta: puede tener otros roles o permisos directos. El acceso al panel se configura por separado en la cuenta.

## Tablero de resultados

El tablero general está en Administración y se muestra a quienes pueden consultar o modificar resultados. La API de consulta mantiene sus permisos actuales y sigue siendo pública; mover el tablero no restringe el acceso directo a los datos.

## Constructor visual de cuestionarios

En Administración → Cuestionarios → Agregar se puede preparar un borrador con preguntas y opciones en una sola pantalla. Los ejemplos son ficticios y no representan instrumentos validados. El constructor funciona solo en el navegador: permite previsualizar el borrador, pero **no lo guarda en la base de datos**.

Un archivo JSON compatible tiene esta estructura; el orden de los arreglos indica el orden de preguntas y opciones:

```json
{
  "titulo": "Ejemplo",
  "tipo": "VARK",
  "descripcion": "",
  "instrucciones": "",
  "preguntas": [
    {
      "texto": "Pregunta de ejemplo",
      "opciones": [
        {"texto": "Primera opción", "dimension": "V"},
        {"texto": "Segunda opción", "dimension": "A"}
      ]
    }
  ]
}
```

Para integrarlo después se necesita un backend que valide y guarde el cuestionario, sus preguntas y sus opciones en una sola operación, verificando los permisos del administrador. Actualmente no existe un endpoint para importar este borrador.

## Evaluación de prueba

En Administración → Evaluaciones se puede responder un ejemplo ficticio o cargar un archivo JSON compatible. La simulación identifica las preferencias más frecuentes al completar el cuestionario; en personalidad señala los empates y las dimensiones sin información. El perfil es orientativo, no está basado en un instrumento validado y no se guarda. Para una aplicación real se necesitan los instrumentos, sus criterios de interpretación y un backend que valide y registre la evaluación completa.

## Pruebas de interfaz

Las pruebas del panel comprueban las páginas renderizadas, los enlaces y los permisos visibles. No ejecutan JavaScript ni sustituyen las pruebas en un navegador.

Para ejecutarlas en PowerShell con una base temporal en memoria, sin modificar la base de vista previa:

Primero abre la terminal en la carpeta raíz del proyecto, donde se encuentra `manage.py`. Si estás en otra carpeta, usa `Set-Location 'C:\ruta\a\vark-personalidad'`, sustituyendo esa ruta por la ubicación del proyecto en tu equipo.

```powershell
$env:DJANGO_SECRET_KEY='local-development-key'; $env:DB_NAME='preview'; $env:DB_USER='preview'; $env:DB_PASSWORD='preview'; $env:DB_HOST='127.0.0.1'; $env:DB_PORT='5432'
python -c "import config.settings as s; s.DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}; import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from django.core.management import execute_from_command_line; execute_from_command_line(['manage.py','test','apps.dashboard','--verbosity','1'])"
```
