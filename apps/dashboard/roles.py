"""Plantillas de rol compartidas por los formularios de roles y de usuarios."""

from django.contrib.auth.models import Group, Permission
from django.db.models import Q

_CONSULTA = [
    ("students", "view_estudiante"), ("students", "view_grupo"),
    ("sessions", "view_session"),
    ("questionnaires", "view_cuestionario"), ("questionnaires", "view_pregunta"),
    ("questionnaires", "view_opcion"),
    ("assessments", "view_evaluacion"), ("assessments", "view_respuesta"),
    ("assessments", "view_seleccionrespuesta"),
    ("results", "view_resultado"), ("results", "view_puntajedimension"),
]

PLANTILLAS_ROL = {
    "administrador": {
        "name": "Administrador",
        "description": "Todos los permisos de administración.",
        "all": True,
        "staff": True,
    },
    "coordinador": {
        "name": "Coordinador",
        "description": "Gestión académica: estudiantes, grupos y evaluaciones.",
        "permissions": _CONSULTA + [
            ("students", "add_estudiante"), ("students", "change_estudiante"),
            ("students", "add_grupo"), ("students", "change_grupo"),
            ("sessions", "add_session"), ("sessions", "change_session"),
            ("assessments", "add_evaluacion"), ("assessments", "change_evaluacion"),
        ],
        "staff": True,
    },
    "docente": {
        "name": "Docente",
        "description": "Consulta y aplicación de evaluaciones.",
        "permissions": _CONSULTA + [("assessments", "add_evaluacion")],
        "staff": True,
    },
    "consultor": {
        "name": "Consultor / Psicopedagogo",
        "description": "Solo consulta de información y resultados.",
        "permissions": _CONSULTA,
        "staff": True,
    },
    "estudiante": {
        "name": "Estudiante",
        "description": "Sin permisos de administración.",
        "permissions": [],
        "staff": False,
    },
}


def permisos_de_plantilla(clave):
    plantilla = PLANTILLAS_ROL[clave]
    if plantilla.get("all"):
        return Permission.objects.all()
    filtro = Q(pk__in=[])
    for app_label, codename in plantilla["permissions"]:
        filtro |= Q(content_type__app_label=app_label, codename=codename)
    return Permission.objects.filter(filtro)


def obtener_rol_de_plantilla(clave):
    """Devuelve el rol de la plantilla; si no existe, lo crea con sus permisos.

    Un rol existente con el mismo nombre se reutiliza sin modificar sus permisos.
    """
    plantilla = PLANTILLAS_ROL[clave]
    rol, creado = Group.objects.get_or_create(name=plantilla["name"])
    if creado:
        rol.permissions.set(permisos_de_plantilla(clave))
    return rol


def sincronizar_roles(crear=False, ajustar_usuarios=False):
    """Deja los permisos de cada rol de plantilla exactamente como los define su plantilla.

    - ``crear``: crea los roles de plantilla que aún no existen.
    - ``ajustar_usuarios``: también ajusta el acceso al panel (is_staff) de las cuentas
      con ese rol; los superusuarios no se tocan.

    Devuelve una lista de (nombre, agregados, quitados, cuentas_ajustadas).
    """
    cambios = []
    for clave, plantilla in PLANTILLAS_ROL.items():
        if crear:
            rol, _ = Group.objects.get_or_create(name=plantilla["name"])
        else:
            rol = Group.objects.filter(name=plantilla["name"]).first()
            if rol is None:
                continue
        esperados = set(permisos_de_plantilla(clave).values_list("pk", flat=True))
        actuales = set(rol.permissions.values_list("pk", flat=True))
        agregados, quitados = esperados - actuales, actuales - esperados
        if agregados or quitados:
            rol.permissions.set(esperados)
        ajustadas = 0
        if ajustar_usuarios:
            ajustadas = rol.user_set.filter(is_superuser=False).exclude(
                is_staff=plantilla["staff"]
            ).update(is_staff=plantilla["staff"])
        cambios.append((plantilla["name"], len(agregados), len(quitados), ajustadas))
    return cambios


PREFIJO_ROL_PERSONALIZADO = "grupo-"


def _nombres_de_plantilla():
    return [p["name"] for p in PLANTILLAS_ROL.values()]


def opciones_de_rol(puede_crear_roles):
    """Opciones del selector de rol: plantillas y roles personalizados existentes.

    Una plantilla cuyo rol aún no existe solo se ofrece si la persona puede crear roles.
    """
    existentes = set(Group.objects.filter(name__in=_nombres_de_plantilla()).values_list("name", flat=True))
    opciones = [
        (clave, plantilla["name"])
        for clave, plantilla in PLANTILLAS_ROL.items()
        if plantilla["name"] in existentes or puede_crear_roles
    ]
    personalizados = Group.objects.exclude(name__in=_nombres_de_plantilla()).order_by("name")
    opciones += [(f"{PREFIJO_ROL_PERSONALIZADO}{rol.pk}", rol.name) for rol in personalizados]
    return opciones


def valor_de_rol(usuario):
    """Valor del selector que corresponde al rol actual de la cuenta."""
    roles = list(usuario.groups.all())
    por_nombre = {plantilla["name"]: clave for clave, plantilla in PLANTILLAS_ROL.items()}
    for rol in roles:
        if rol.name in por_nombre:
            return por_nombre[rol.name]
    return f"{PREFIJO_ROL_PERSONALIZADO}{roles[0].pk}" if roles else ""


def resolver_rol(valor):
    """Devuelve (rol, acceso_al_panel) para un valor del selector; crea el rol de plantilla si falta."""
    if valor in PLANTILLAS_ROL:
        return obtener_rol_de_plantilla(valor), PLANTILLAS_ROL[valor]["staff"]
    pk = valor.removeprefix(PREFIJO_ROL_PERSONALIZADO)
    return Group.objects.get(pk=pk), True


def acceso_al_panel(valor):
    if valor in PLANTILLAS_ROL:
        return PLANTILLAS_ROL[valor]["staff"]
    return True


def roles_para_vista_previa():
    """Plantillas y roles personalizados con sus permisos, para el panel de vista previa."""
    datos = plantillas_para_vista_previa()
    personalizados = Group.objects.exclude(name__in=_nombres_de_plantilla()).prefetch_related(
        "permissions__content_type"
    )
    for rol in personalizados:
        datos.append({
            "key": f"{PREFIJO_ROL_PERSONALIZADO}{rol.pk}",
            "name": rol.name,
            "description": "Rol personalizado.",
            "staff": True,
            "exists": True,
            "all_permissions": False,
            "permissions": [str(p) for p in rol.permissions.all()],
        })
    return datos


def plantillas_para_vista_previa():
    """Datos de las plantillas para los paneles de vista previa (JSON)."""
    existentes = {
        rol.name: rol
        for rol in Group.objects.filter(
            name__in=[p["name"] for p in PLANTILLAS_ROL.values()]
        ).prefetch_related("permissions__content_type")
    }
    datos = []
    for clave, plantilla in PLANTILLAS_ROL.items():
        todos = bool(plantilla.get("all"))
        definidos = [] if todos else list(permisos_de_plantilla(clave).select_related("content_type"))
        existente = existentes.get(plantilla["name"])
        if existente is not None:
            # El rol ya existe: se reutiliza tal como está configurado.
            actuales = [str(p) for p in existente.permissions.all()]
            todos_actuales = False
        else:
            actuales = [str(p) for p in definidos]
            todos_actuales = todos
        datos.append({
            "key": clave,
            "name": plantilla["name"],
            "description": plantilla["description"],
            "staff": plantilla["staff"],
            "exists": existente is not None,
            "group_id": existente.pk if existente is not None else None,
            "all": todos,
            "permission_ids": [str(p.pk) for p in definidos],
            "all_permissions": todos_actuales,
            "permissions": actuales,
        })
    return datos
