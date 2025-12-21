from .models import *

def permission_state(user, code):
    if user.is_superuser or user.role == "owner":
        return {"enabled": True, "source": "role"}

    if RolePermission.objects.filter(
        role=user.role, permission__code=code
    ).exists():
        return {"enabled": True, "source": "role"}

    if UserPermission.objects.filter(
        user=user, permission__code=code
    ).exists():
        return {"enabled": True, "source": "user"}

    return {"enabled": False, "source": "none"}
