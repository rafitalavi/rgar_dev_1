from accounts.models import User
from permissions_app.services import has_permission

def get_effective_user(request):
    """
    Returns (effective_user, is_impersonating)
    """
    impersonate_id = request.headers.get("X-Impersonate-User")

    if not impersonate_id:
        return request.user, False

    if not has_permission(request.user, "chat:impersonate"):
        raise PermissionError("Impersonation not allowed")

    try:
        target = User.objects.get(id=int(impersonate_id), is_deleted=False)
    except User.DoesNotExist:
        raise PermissionError("Invalid impersonated user")

    return target, True
