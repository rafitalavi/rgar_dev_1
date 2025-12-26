from rest_framework import serializers
from .models import Assessment, Question, Answer, AssesmentNotification


class AssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = [
            "id",
            "title",
            "description",
            "clinic",
            "role",
            "status",
            "start_date",
            "end_date",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
           
            "created_at",
        ]


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "number", "text"]
        read_only_fields = ["id", "number"]  # number is auto-assigned


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ["id", "answer_text"]
        read_only_fields = ["id"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssesmentNotification
        fields = ["id", "title", "message", "is_read", "created_at"]
