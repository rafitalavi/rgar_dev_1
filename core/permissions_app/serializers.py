# permissions_app/serializers.py

from rest_framework import serializers


class PermissionItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    enabled = serializers.BooleanField()
    source = serializers.ChoiceField(
        choices=["role", "user", "none"]
    )

class PermissionGroupSerializer(serializers.Serializer):
    group = serializers.CharField()
    label = serializers.CharField()
    permissions = PermissionItemSerializer(many=True)


class TogglePermissionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    permission_code = serializers.CharField()
    enabled = serializers.BooleanField()
