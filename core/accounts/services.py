from rest_framework_simplejwt.token_blacklist.models import (
    OutstandingToken,
    BlacklistedToken,
)


def logout_user_everywhere(user):
    """
    Force logout user from all devices by blacklisting refresh tokens
    """
    tokens = OutstandingToken.objects.filter(user=user)

    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)


def deactivate_user(user):
    """
    Soft delete user + deactivate + logout everywhere
    """
    user.is_active = False
    user.is_deleted = True
    user.save(update_fields=["is_active", "is_deleted"])

    logout_user_everywhere(user)
