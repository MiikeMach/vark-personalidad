5. Pruebas
5.1 Estrategia
- Pruebas de servicios (TestCase y SimpleTestCase): verifican reglas de negocio sin pasar por HTTP.
- Pruebas de integración HTTP (TestCase): usan self.client para ejercitar la API completa.
- Aislamiento: cada clase crea sus datos en setUpTestData; los tests de auth usan post('/api/auth/login/'); el resto usa force_login.
- Correo: ContactoAPITests sobrescribe EMAIL_BACKEND a locmem para inspeccionar mail.outbox.
Ejecución local:

$env:DJANGO_SECRET_KEY='local-development-key'; $env:DB_NAME='preview'; $env:DB_USER='preview'; $env:DB_PASSWORD='preview'; $env:DB_HOST='127.0.0.1'; $env:DB_PORT='5432'
python -c "import config.settings as s; s.DATABASES={'default': {'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}; import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; from django.core.management import execute_from_command_line; execute_from_command_line(['manage.py','test','apps','--verbosity','1'])"

5.2 Qué hace cada prueba

5.2.1 apps.assessments.tests
Clase	Propósito
ValidarSeleccionesTests	Verifica que validar_selecciones, guardar_respuesta y guardar_respuesta_personalidad acepten/rechacen correctamente: múltiples opciones VARK, omisiones, opciones ajenas, duplicados, restricción de una opción en personalidad, identificadores inválidos, reemplazo de selecciones, evaluación finalizada y distribución inválida.
ValidarEvaluacionEditableTests	Comprueba que solo las evaluaciones EN_PROGRESO admitan cambios y que las FINALIZADA se rechacen.
ValidarDistribucionPersonalidadTests	Comprueba que la distribución de puntos acepte 7/3 y 10/0, y rechace 5/5, sumas distintas de 10, valores fuera de rango, no enteros y booleanos.
ValidarParPersonalidadTests	Comprueba que solo se acepten los pares E/I, S/N, T/F, J/P (en cualquier orden) y se rechacen pares cruzados, repetidos o dimensiones VARK.
GuardarRespuestaPersonalidadTests	Comprueba el guardado y la actualización de la distribución sin duplicar selecciones, que un error no modifique la respuesta previa, que se rechacen pares inválidos y que no se pueda modificar una evaluación finalizada.

5.2.2 apps.results.tests
Clase	Propósito
GuardarResultadoTests	Comprueba el cálculo y guardado de resultados: VARK con omisiones, personalidad con perfil, no duplicar resultados al recalcular, actualizar puntajes existentes, generar perfil ENTJ, devolver Perfil no determinado por empate o datos incompletos.
ValidarRespuestasParaFinalizarTests	Comprueba la reversión transaccional si falla el guardado, que VARK permita omisiones, que personalidad completa sea válida y sin responder sea inválida, que una distribución 5/5 se rechace, que una opción de otra pregunta se rechace, y que finalizar_evaluacion cierre correctamente y no permita finalizar dos veces.

5.2.3 apps.scoring.tests
Clase	Propósito
CalcularPuntajesVarkTests	Comprueba que VARK sin respuestas devuelva ceros, que cuente las cuatro dimensiones, que una pregunta omitida no sume, que actualizar una respuesta no duplique puntajes y que se rechace un cuestionario de personalidad.
CalcularPuntajesPersonalidadTests	Comprueba que personalidad sin respuestas devuelva ceros, que sume las ocho dimensiones, que actualizar no duplique puntos y que se rechace una evaluación VARK.
GenerarPerfilPersonalidadTests	Comprueba la generación de perfiles ENTJ e ISFP, que un empate devuelva None, que datos incompletos devuelvan None y que se rechacen puntuaciones negativas o no enteras.

5.2.4 apps.api.tests
Clase	Propósito
FlujoEvaluacionAPITests	Comprueba el flujo HTTP completo: guardar y finalizar VARK, guardar personalidad con puntos y finalizar, rechazar personalidad inválida sin guardar, no recalcular una evaluación finalizada, que /calcular/ devuelva el resultado esperado y que un usuario sin permisos reciba 403.
AuthAPITests	Comprueba me sin sesión (401), login correcto (200) y me (200), login incorrecto (401), login de usuario inactivo (401) y logout (200) con me posterior (401).
RequireStaffTests	Comprueba que responder y calcular devuelvan 401 sin sesión, 403 para no staff y que staff pase el decorador (404 si el recurso no existe).
CuestionarioCompletoAPITests	Comprueba que /completo/ devuelva preguntas y opciones anidadas (200) y 404 si no existe.
AgregadosAPITests	Comprueba la estructura del payload agregado (total, grupal, individual), la validación de alcance y tipo, y que individual requiera estudiante.
BuscarAPITests	Comprueba que q válido devuelva estudiantes y grupos, que q corto o ausente devuelva 400.
PdfAPITests	Comprueba que el PDF individual y el múltiple devuelvan application/pdf, cabecera %PDF-, nombre de archivo correcto y contenido no vacío.
ContactoAPITests	Comprueba que un payload válido devuelva 201 y envíe un correo, que un payload inválido devuelva 400 con errores por campo y no envíe correo, y que un fallo de send_mail devuelva 500.

5.2.5 apps.dashboard.tests
Clase	Propósito
RolesAdminTests	Comprueba la creación de roles y la asignación de usuarios sin eliminar otros roles, la asignación a roles existentes sin cambiar permisos, que sin permiso de usuario no se pueda asignar, que un usuario inválido no se asigne, que un error de edición no cambie permisos ni asigne usuario, que la lista muestre acciones por fila con confirmación, que las listas de usuarios y grupos escolares tengan acciones, que sin permiso no se muestre ni permita eliminar, que en popup no se muestren acciones y que "Ver usuarios" filtre correctamente y requiera permiso de consulta.
CambioContrasenaAdminTests	Comprueba que el formulario de cambio de contraseña y su confirmación no incluyan selector de tema y que los errores de contraseña se muestren correctamente.
TableroResultadosTests	Comprueba que el tablero no aparezca en inicio y que en el admin requiera el permiso view_resultado.
FiltrosAdminTests	Comprueba que las listas no tengan filtros de fecha, que la lista de usuarios conserve filtros de gestión sin superusuario, y que los recuentos sean siempre visibles y sin selector.
InterfazFrontendTests	Comprueba que el panel muestre enlaces a los apartados de gestión, que solo muestre apartados permitidos, que el inicio ofrezca formulario de evaluación y acceso, que el constructor ofrezca vista previa sin descarga, y que "Opciones seleccionadas" muestre detalles de la respuesta.

5.3 Cobertura por módulo
+---------------------+------------------+------------------+
| Módulo              | Servicios        | API/HTTP         |
+---------------------+------------------+------------------+
| assessments         | Sí               | Sí (flujo)       |
| results             | Sí               | Sí (flujo)       |
| scoring             | Sí               | Indirecto        |
| api (auth, PDF,     | —                | Sí               |
| contacto, buscar)   |                  |                  |
| dashboard           | —                | Sí (admin)       |
| questionnaires      | No (pendiente)   | Parcial          |
| students            | No (pendiente)   | Parcial          |
| accounts            | No (pendiente)   | —                |
+---------------------+------------------+------------------+