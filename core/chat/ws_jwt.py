# # from urllib.parse import parse_qs
# # from django.contrib.auth.models import AnonymousUser
# # from channels.db import database_sync_to_async
# # from rest_framework_simplejwt.authentication import JWTAuthentication

# # @database_sync_to_async
# # def get_user_from_jwt(token: str):
# #     jwt_auth = JWTAuthentication()
# #     validated = jwt_auth.get_validated_token(token)
# #     return jwt_auth.get_user(validated)

# # class JwtAuthMiddleware:
# #     """
# #     Accepts JWT token from:
# #     ws://.../ws/chat/ROOM_ID/?token=JWT
# #     """
# #     def __init__(self, app):
# #         self.app = app

# #     async def __call__(self, scope, receive, send):
# #         scope["user"] = AnonymousUser()

# #         qs = parse_qs(scope.get("query_string", b"").decode())
# #         token = (qs.get("token") or [None])[0]

# #         if token:
# #             try:
# #                 scope["user"] = await get_user_from_jwt(token)
# #             except Exception:
# #                 scope["user"] = AnonymousUser()

# #         return await self.app(scope, receive, send)

# # def JwtAuthMiddlewareStack(inner):
# #     return JwtAuthMiddleware(inner)



# # chat_app/middleware.py
# from channels.middleware import BaseMiddleware  # Channels 4.x
# from django.contrib.auth.models import AnonymousUser
# from urllib.parse import parse_qs
# from rest_framework_simplejwt.tokens import UntypedToken
# from jwt import decode as jwt_decode
# from django.conf import settings
# from channels.db import database_sync_to_async

# class JwtAuthMiddleware(BaseMiddleware):
#     async def __call__(self, scope, receive, send):
#         # Lazy import here
#         from django.contrib.auth import get_user_model
#         from django.contrib.auth.models import AnonymousUser

#         User = get_user_model()

#         # Extract token from query string
#         query_string = parse_qs(scope['query_string'].decode())
#         token = query_string.get('token', [None])[0]

#         if token is not None:
#             try:
#                 # Validate token
#                 UntypedToken(token)
#                 payload = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
#                 user_id = payload.get('user_id')

#                 # Fetch user
#                 scope['user'] = await database_sync_to_async(User.objects.get)(id=user_id)
#             except Exception:
#                 scope['user'] = AnonymousUser()
#         else:
#             scope['user'] = AnonymousUser()

#         return await super().__call__(scope, receive, send)
# chat/ws_jwt.py

from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.db import close_old_connections
from rest_framework_simplejwt.authentication import JWTAuthentication


@database_sync_to_async
def get_user_from_token(token: str):
    jwt_auth = JWTAuthentication()
    validated_token = jwt_auth.get_validated_token(token)
    return jwt_auth.get_user(validated_token)


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        close_old_connections()

        scope["user"] = AnonymousUser()  # ALWAYS set default

        try:
            query_string = parse_qs(scope.get("query_string", b"").decode())
            token = query_string.get("token", [None])[0]

            if token:
                scope["user"] = await get_user_from_token(token)

        except Exception:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
