from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ActiveUserJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        if not user.is_active or user.is_deleted:
            raise AuthenticationFailed(
                "User account is inactive or deleted"
            )

        return user
