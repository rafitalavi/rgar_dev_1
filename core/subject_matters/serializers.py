from rest_framework import serializers
from .models import SubjectMatters

class SubjectMattersSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubjectMatters
        fields = ("id", "title", "description")

    def validate_title(self, value):
        qs = SubjectMatters.objects.filter(title__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Subject already exists.")
        return value
