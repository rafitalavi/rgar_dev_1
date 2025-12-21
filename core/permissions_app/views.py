from django.shortcuts import render
from accounts.models import *
# Create your views here.
# permissions_app/views.py
from .models import *
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import *
from .constants import PERMISSION_GROUPS
from .utils import permission_state
from .serializers import PermissionGroupSerializer


class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        target_user = User.objects.get(id=user_id)

        result = []

        for group_key, group in PERMISSION_GROUPS.items():
            perms = []

            for code in group["permissions"]:
                state = permission_state(target_user, code)

                perms.append({
                    "code": code,
                    "label": code.replace(":", " ").replace("_", " ").title(),
                    "enabled": state["enabled"],
                    "source": state["source"],
                })

            result.append({
                "group": group_key,
                "label": group["label"],
                "permissions": perms,
            })

        serializer = PermissionGroupSerializer(result, many=True)
        return Response(serializer.data)


class ToggleUserPermissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role not in ["owner", "president"]:
            return Response(
                {"message": "Forbidden"},
                status=403
            )

        serializer = TogglePermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.objects.get(id=serializer.validated_data["user_id"])
        code = serializer.validated_data["permission_code"]
        enabled = serializer.validated_data["enabled"]

        perm = Permission.objects.get(code=code)

        # 🔒 NO OVERRIDE: role permissions are locked
        if RolePermission.objects.filter(
            role=user.role, permission=perm
        ).exists():
            return Response({"success": True})

        if enabled:
            UserPermission.objects.get_or_create(
                user=user, permission=perm
            )
        else:
            UserPermission.objects.filter(
                user=user, permission=perm
            ).delete()

        return Response({"success": True})
