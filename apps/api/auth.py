"""Helpers de autenticación y permisos para la API."""

from functools import wraps
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout


def user_to_dict(user):
    if not user or not user.is_authenticated:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


def require_staff(view_method):
    """
    Decorador para métodos de vista: exige usuario autenticado y staff.
    Devuelve 401 si no autenticado, 403 si autenticado pero no staff.
    """
    @wraps(view_method)
    def _wrapped(self, request, *args, **kwargs):
        user = request.user
        if not user or not user.is_authenticated:
            return JsonResponse(
                {"detail": "Autenticación requerida."}, status=401
            )
        if not user.is_staff:
            return JsonResponse(
                {"detail": "Se requieren permisos de administrador."}, status=403
            )
        return view_method(self, request, *args, **kwargs)
    return _wrapped