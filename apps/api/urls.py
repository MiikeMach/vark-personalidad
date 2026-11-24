from django.urls import path

from . import views

urlpatterns = [
    # auth
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),

    # students
    path("grupos/", views.GrupoListView.as_view()),
    path("grupos/<int:pk>/", views.GrupoDetailView.as_view()),
    path("estudiantes/", views.EstudianteListView.as_view()),
    path("estudiantes/<int:pk>/", views.EstudianteDetailView.as_view()),

    # questionnaires
    path("cuestionarios/", views.CuestionarioListView.as_view()),
    path("cuestionarios/<int:pk>/", views.CuestionarioDetailView.as_view()),
    path("cuestionarios/<int:pk>/completo/", views.CuestionarioCompletoView.as_view()),
    path("preguntas/", views.PreguntaListView.as_view()),
    path("preguntas/<int:pk>/", views.PreguntaDetailView.as_view()),
    path("opciones/", views.OpcionListView.as_view()),
    path("opciones/<int:pk>/", views.OpcionDetailView.as_view()),

    # assessments
    path("evaluaciones/", views.EvaluacionListView.as_view()),
    path("evaluaciones/iniciar/", views.EvaluacionIniciarView.as_view()),
    path("evaluaciones/<int:pk>/", views.EvaluacionDetailView.as_view()),
    path("evaluaciones/<int:pk>/responder/", views.EvaluacionResponderView.as_view()),
    path("evaluaciones/<int:pk>/calcular/", views.EvaluacionCalcularView.as_view()),
    path("respuestas/", views.RespuestaListView.as_view()),
    path("respuestas/<int:pk>/", views.RespuestaDetailView.as_view()),
    path("selecciones/", views.SeleccionListView.as_view()),
    path("selecciones/<int:pk>/", views.SeleccionDetailView.as_view()),

    # results
    path("buscar/", views.BuscarView.as_view()),
    path("resultados/", views.ResultadoListView.as_view()),
    path("resultados/agregados/", views.ResultadoAgregadosView.as_view()),
    path("resultados/pdf/", views.ResultadosPdfView.as_view()),
    path("resultados/<int:pk>/pdf/", views.ResultadoPdfView.as_view()),
    path("resultados/<int:pk>/", views.ResultadoDetailView.as_view()),
    path("dashboard/grupal/", views.DashboardGrupalView.as_view()),
    path("puntajes/", views.PuntajeListView.as_view()),
    path("puntajes/<int:pk>/", views.PuntajeDetailView.as_view()),
    # contacto (#11)
    path("contacto/", views.ContactoView.as_view()),
]