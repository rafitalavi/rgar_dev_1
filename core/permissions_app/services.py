from .models import RolePermission, UserPermission

def has_permission(user, code):
    if not user or not user.is_authenticated:
        return False

    # Owner or superuser: always allowed
    if user.is_superuser or user.role == "owner":
        return True

    if UserPermission.objects.filter(user=user, permission__code=code).exists():
        return True

    return RolePermission.objects.filter(
        role=user.role, permission__code=code
    ).exists()