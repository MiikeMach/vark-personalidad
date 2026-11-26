# Anexo C. Limitaciones conocidas y trabajo futuro
## C.1. Limitaciones conocidas

1. **`apps.accounts`, `apps.contact` y `apps.reports`** son esqueletos; su lógica vive en `apps.api` o en `auth.User`. Se recomienda consolidarlas si el proyecto crece.
2. **`Opcion.dimension`** mezcla dimensiones VARK y personalidad; la compatibilidad con el tipo de cuestionario se valida al guardar respuestas, no al crear opciones. Conviene añadir una validación a nivel de modelo o de `clean()`.
3. **`SeleccionRespuesta.puntos`** no tiene restricción de rango en BD; la regla 0–10 y suma 10 se aplica en servicios.
4. **Personalidad** exige que **todas** las preguntas estén contestadas para finalizar; VARK permite omisiones. Es una decisión de negocio que debe documentarse en la interfaz.
5. **`Resultado.interpretacion`** queda vacío en VARK; solo se llena en personalidad. Podría añadirse una interpretación textual del perfil dominante.
6. **`ALLOWED_HOSTS = []`** y **`DEBUG = True`** son adecuados para desarrollo local, no para producción.
7. **`BaseListView.get()`** contiene un `return` duplicado (código muerto).
8. **Sin DRF**: la API es funcional pero manual; migrar a DRF facilitaría validación, serialización y documentación automática.
9. **Sin pruebas de navegador**: las pruebas de interfaz no ejecutan JavaScript.
10. **El estudiante no es un usuario autenticable**: las evaluaciones las inicia el administrador.
11. **El constructor visual y la evaluación de prueba no persisten** en la base de datos; son herramientas de demostración en el navegador.

## C.2. Trabajo futuro

- Consolidar `apps.accounts`, `apps.contact` y `apps.reports`.
- Añadir validación de dimensión por tipo de cuestionario a nivel de modelo.
- Añadir restricciones `CHECK` en BD para `puntos` (0–10 y suma 10 por respuesta).
- Implementar autenticación de estudiantes y asignación de evaluaciones.
- Añadir interpretación textual VARK.
- Migrar la API a DRF con OpenAPI/Swagger.
- Añadir pruebas de navegador (Playwright/Selenium).
- Configurar `DEBUG=False`, `ALLOWED_HOSTS`, HTTPS y variables de entorno para producción.
- Añadir CI (GitHub Actions) para ejecutar pruebas en cada PR.
- Persistir el constructor visual de cuestionarios (endpoint de importación).