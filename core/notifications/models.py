from django.db import models
from django.conf import settings
User = settings.AUTH_USER_MODEL

class Notification(models.Model):
    TYPE = (("mention","Mention"), ("system","System"))
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    notif_type = models.CharField(max_length=20, choices=TYPE)
    title = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict)  # {"room_id":..,"message_id":..}
    is_seen = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "is_seen", "-created_at"])]

