from rest_framework import serializers
from .models import Assessment, Question, Answer, AssesmentNotification , Score
from accounts.models import User

from django.db.models import Avg, F, FloatField, ExpressionWrapper


class AssessmentSerializer(serializers.ModelSerializer):
    created_by_user = serializers.SerializerMethodField(read_only=True)
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
            'created_by_user' 
        ]
        read_only_fields = [
            "id",
            "status",
           
            "created_at",
        ]
    def get_created_by_user(self, obj):
        user = obj.created_by
        if not user:
            return None
        
        return {
            'id': user.id,
            'name':  user.first_name,
            'role': self._get_user_role(user)
        }
    
    def _get_user_role(self, user):
        """Extract user role based on your user model structure"""
        # Option 1: If User model has a role field
        if hasattr(user, 'role') and user.role:
            return user.role
        
        # Option 2: If role is in UserProfile
        if hasattr(user, 'profile') and hasattr(user.profile, 'role') and user.profile.role:
            return user.profile.role
        
        # Option 3: Get role from groups (Django default)
        if user.groups.exists():
            return user.groups.first().name
        
        # Option 4: Based on user permissions
        if user.is_superuser:
            return "Super Admin"
        elif user.is_staff:
            return "Staff"
        
        # Default
        return "User"
    
class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ["id", "number", "text"]
        read_only_fields = ["id", "number"]  


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = ["id", "answer_text"]
        read_only_fields = ["id"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssesmentNotification
        fields = ["id", "title", "message", "is_read", "created_at"]




class CreatorAssessmentHistorySerializer(serializers.ModelSerializer):
    total_members = serializers.IntegerField(read_only=True)
    completed_members = serializers.IntegerField(read_only=True)
    average_score = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    created_by_user = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Assessment
        fields = [
            "id",
            "title",
            "role",
            "status",
            "due_date",
            "total_members",
            "completed_members",
            "average_score",
            "created_by",
            'created_by_user',
        ]

    def get_due_date(self, obj):
        return obj.end_date.date() if obj.end_date else None

    def get_average_score(self, obj):
        scores = Score.objects.filter(assessment=obj)

        if not scores.exists():
            return 0

        avg = scores.aggregate(
            avg=Avg(
                ExpressionWrapper(
                    F("total_score") * 100.0 / F("max_score"),
                    output_field=FloatField(),
                )
            )
        )["avg"]

        return round(avg or 0)
    def get_created_by_user(self, obj):
        user = obj.created_by
        if not user:
            return None
        
        return {
            'id': user.id,
            'name':  user.first_name,
            'role': self._get_user_role(user)
        }
    
    def _get_user_role(self, user):
        """Extract user role based on your user model structure"""
        # Option 1: If User model has a role field
        if hasattr(user, 'role') and user.role:
            return user.role
        
        # Option 2: If role is in UserProfile
        if hasattr(user, 'profile') and hasattr(user.profile, 'role') and user.profile.role:
            return user.profile.role
        
        # Option 3: Get role from groups (Django default)
        if user.groups.exists():
            return user.groups.first().name
        
        # Option 4: Based on user permissions
        if user.is_superuser:
            return "Super Admin"
        elif user.is_staff:
            return "Staff"
        
        # Default
        return "User"
