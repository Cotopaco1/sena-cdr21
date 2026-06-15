ROLE_ADMINISTRADOR = 'Administrador'
ROLE_VENDEDOR = 'Vendedor'
ROLE_GERENTE = 'Gerente'

ROLE_NAMES = [
    ROLE_ADMINISTRADOR,
    ROLE_VENDEDOR,
    ROLE_GERENTE,
]

USER_MANAGER_ROLES = [
    ROLE_ADMINISTRADOR,
    ROLE_GERENTE,
]

PERM_MANAGE_INVENTORY = 'manage_inventory'
PERM_MANAGE_PURCHASES = 'manage_purchases'
PERM_MANAGE_SALES = 'manage_sales'
PERM_MANAGE_CLIENTS = 'manage_clients'
PERM_MANAGE_SETTINGS = 'manage_settings'
PERM_MANAGE_USERS = 'manage_users'

ROLE_PERMISSIONS = {
    ROLE_ADMINISTRADOR: {
        PERM_MANAGE_INVENTORY,
        PERM_MANAGE_PURCHASES,
        PERM_MANAGE_SALES,
        PERM_MANAGE_CLIENTS,
        PERM_MANAGE_SETTINGS,
        PERM_MANAGE_USERS,
    },
    ROLE_GERENTE: {
        PERM_MANAGE_INVENTORY,
        PERM_MANAGE_PURCHASES,
        PERM_MANAGE_SALES,
        PERM_MANAGE_CLIENTS,
        PERM_MANAGE_SETTINGS,
        PERM_MANAGE_USERS,
    },
    ROLE_VENDEDOR: {
        PERM_MANAGE_SALES,
        PERM_MANAGE_CLIENTS,
    },
}

ALL_PERMISSIONS = {
    PERM_MANAGE_INVENTORY,
    PERM_MANAGE_PURCHASES,
    PERM_MANAGE_SALES,
    PERM_MANAGE_CLIENTS,
    PERM_MANAGE_SETTINGS,
    PERM_MANAGE_USERS,
}


def get_user_permissions(user):
    if not user.is_authenticated:
        return set()

    if user.is_superuser:
        return set(ALL_PERMISSIONS)

    role_names = user.groups.values_list('name', flat=True)
    permissions = set()

    for role_name in role_names:
        permissions.update(ROLE_PERMISSIONS.get(role_name, set()))

    return permissions


def user_can(user, permission):
    return permission in get_user_permissions(user)


def user_can_any(user, permissions):
    return bool(get_user_permissions(user).intersection(permissions))


def get_user_permission_flags(user):
    permissions = get_user_permissions(user)

    return {
        'can_manage_inventory': PERM_MANAGE_INVENTORY in permissions,
        'can_manage_purchases': PERM_MANAGE_PURCHASES in permissions,
        'can_manage_sales': PERM_MANAGE_SALES in permissions,
        'can_manage_clients': PERM_MANAGE_CLIENTS in permissions,
        'can_manage_settings': PERM_MANAGE_SETTINGS in permissions,
        'can_manage_users': PERM_MANAGE_USERS in permissions,
    }
