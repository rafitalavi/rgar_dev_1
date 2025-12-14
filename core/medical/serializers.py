from rest_framework import serializers
from .models import Clinic

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
    