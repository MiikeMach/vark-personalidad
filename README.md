# vark-personalidad
Plataforma web académica para la aplicación, evaluación y análisis de los instrumentos VARK y de personalidad basados en Jung y Myers-Briggs.

## Roles de acceso

En Administración → Roles de acceso, selecciona una plantilla y revisa sus permisos antes de guardar. Opcionalmente puedes asignar el rol a un usuario existente; esto no elimina sus otros roles ni permisos. Al editar un rol, sus permisos se conservan salvo que elijas otra plantilla y guardes. La lista de roles permite ver sus usuarios.

Los permisos del rol no son necesariamente todos los permisos de una cuenta: puede tener otros roles o permisos directos. El acceso al panel se configura por separado en la cuenta.

Al crear o editar usuarios desde Administración, el nombre de usuario admite espacios además de letras, números y los caracteres `@`, `.`, `+`, `-` y `_`. Para iniciar sesión, escribe el mismo nombre.

En la ficha de edición del usuario se pueden seleccionar sus roles y configurar el acceso al panel sin salir del formulario. Los permisos directos y la opción de superusuario están en «Permisos avanzados»; los permisos directos se suman a los de sus roles.

Al agregar un usuario se pueden registrar sus datos personales y elegir roles existentes. Quienes pueden consultar roles pueden revisar sus permisos desde el formulario antes de asignarlos. El usuario hereda los permisos de esos roles; el acceso al panel debe activarse por separado. La fecha de creación se registra automáticamente.

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

En Administración → Evaluaciones se puede responder un ejemplo ficticio o cargar un archivo JSON compatible. La simulación identifica las preferencias más frecuentes al completar el cuestionario; en personalidad señala los empates y las dimensiones sin información. El perfil es orientativo, no está basado en un instrumento validado y no se guarda. Para registrar una evaluación se usa la sección Instrumentos del sitio y un cuestionario configurado en la base de datos. Para una aplicación real se necesitan instrumentos y criterios de interpretación validados.

En la evaluación registrada de personalidad, cada pregunta debe tener dos opciones de dimensiones opuestas (E/I, S/N, T/F o J/P). Se distribuyen 10 puntos entre ambas, sin reparto 5/5; el sistema guarda las dos puntuaciones y calcula el resultado al finalizar.

Para responder, un administrador registra el grupo y el perfil del estudiante. En Instrumentos, el estudiante selecciona su perfil activo y un cuestionario, sin crear una cuenta. La evaluación iniciada queda asociada a la sesión del navegador para su envío; el personal puede responder cualquier evaluación. Si se pierde la sesión, debe iniciarse una nueva evaluación.

Las solicitudes de inicio y cierre de sesión, inicio de evaluación y envío de respuestas requieren protección CSRF. Los clientes de la API deben obtener el token CSRF y enviarlo en `X-CSRFToken`. Como la selección no verifica la identidad, cualquiera puede elegir el perfil de otra persona y registrar respuestas en su nombre. Los endpoints de consulta existentes siguen siendo públicos y no restringen la lectura de resultados o datos de estudiantes. El campo de vínculo a usuario existente se conserva en la base por compatibilidad, pero no se usa en este flujo.

## Pruebas de interfaz

Las pruebas del panel comprueban las páginas renderizadas, los enlaces y los permisos visibles. No ejecutan JavaScript ni sustituyen las pruebas en un navegador.

Para ejecutarlas en PowerShell con una base temporal en memoria, sin modificar la base de vista previa:

Primero abre la terminal en la carpeta raíz del proyecto, donde se encuentra `manage.py`. Si estás en otra carpeta, usa `Set-Location 'C:\ruta\a\vark-personalidad'`, sustituyendo esa ruta por la ubicación del proyecto en tu equipo.

```powershell
$env:DJANGO_SECRET_KEY='local-development-key'; $env:DB_NAME='preview'; $env:DB_USER='preview'; $env:DB_PASSWORD='preview'; $env:DB_HOST='127.0.0.1'; $env:DB_PORT='5432'
python -c "import config.settings as s; s.DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}; import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from django.core.management import execute_from_command_line; execute_from_command_line(['manage.py','test','apps.dashboard','--verbosity','1'])"
```
