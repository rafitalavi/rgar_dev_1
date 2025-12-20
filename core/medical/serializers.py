from rest_framework import serializers
from .models import Clinic

from accounts.models import User
class ClinicSerializer(serializers.ModelSerializer):
    active_members = serializers.IntegerField(read_only=True)
    class Meta:
        model = Clinic
        fields = (
            "id",
            "name",
            "address",
            "phone_number",
            "fax_number",
            "website",
            "type",
            "active_members",
        )

    def validate_name(self, value):
        value = value.strip()

        queryset = Clinic.objects.filter(name__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A clinic with this name already exists."
            )
        return value
    






class UserLiteSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "role",
        )

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()