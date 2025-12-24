
from django.utils import timezone
from medical.models import Clinic
from accounts.models import User
from django.db import models



class Assessment(models.Model):
    status = models.CharField(
        max_length=20,
        choices=(
            ("draft", "Draft"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("closed", "Closed"),
        ),
        default="draft"
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="assessments")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_assessments")

    is_active = models.BooleanField(default=True)   # pause/start assessment globally
    is_ai_demo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.clinic_id})"


class AssessmentRole(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES)

    class Meta:
        unique_together = ("assessment", "role")


class AssessmentMedia(models.Model):
    FILE = "file"
    AUDIO = "audio"
    TEXT = "text" 
    MEDIA_TYPE_CHOICES = (
        (FILE, "File"),
        (AUDIO, "Audio"),
        (TEXT, "Text"),
    )

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)

    # For file/audio:
    media = models.FileField(upload_to="assessment_media/", null=True, blank=True)

    # For text attachment:
    text = models.TextField(null=True, blank=True)

    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Question(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        unique_together = ("assessment", "number")
        ordering = ["number"]





class UserAssessment(models.Model):
    STATUS = (
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("paused", "Paused"),
        ("completed", "Completed"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=STATUS, default="not_started")
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "assessment")


class Answer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    answer_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "question")


class Score(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)
    score = models.FloatField()
    max_score = models.FloatField()
    feedback = models.TextField(blank=True , null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "assessment")


# class Notification(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     title = models.CharField(max_length=255)
#     message = models.TextField()
#     is_read = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
