from cdr22.services.configuracion import get_configuracion_sistema
from cdr22.roles import get_user_permission_flags


def configuracion_sistema(request):
    return {
        'configuracion_sistema': get_configuracion_sistema()
    }


def permisos_usuario(request):
    return {
        'permisos_usuario': get_user_permission_flags(request.user)
    }
