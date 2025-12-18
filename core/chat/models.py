from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from medical.models import Clinic
from django.utils import timezone
User = settings.AUTH_USER_MODEL


class ChatRoom(models.Model):
    ROOM_TYPE = (
        ("group", "Group"),
        ("private", "Private"),
        ("ai", "AI"),
    )

    GROUP_KIND = (
        ("clinic_all", "Clinic All"),
        ("clinic_role", "Clinic Role"),
    )

    room_type = models.CharField(max_length=10, choices=ROOM_TYPE)

    # only for clinic groups
    group_kind = models.CharField(
        max_length=20,
        choices=GROUP_KIND,
        null=True,
        blank=True
    )

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # only for clinic_role groups
    role = models.CharField(max_length=20, null=True, blank=True)

    name = models.CharField(max_length=200, blank=True)
    unique_key = models.CharField(
        max_length=200,
        null=True,      # ✅ IMPORTANT
        blank=True,
        
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.room_type != "group":
            if self.group_kind or self.role or self.clinic:
                raise ValidationError("Group fields allowed only for group rooms")

        if self.group_kind == "clinic_role" and not self.role:
            raise ValidationError("clinic_role requires role")

        if self.group_kind == "clinic_all" and self.role:
            raise ValidationError("clinic_all cannot have role")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.room_type}:{self.name or self.unique_key}"



#Room membership & state (SOFT DELETE LIVES HERE)
class ChatParticipant(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("room", "user")


class RoomUserState(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="user_states")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    last_read_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ("room", "user")
        indexes = [models.Index(fields=["user", "room", "is_deleted"])]
        
#Message

        
class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    content = models.TextField(blank=True)
    is_ai = models.BooleanField(default=False)
    parent_message = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["room", "-id"])]


#Attachments
class MessageAttachment(models.Model):
    ATTACHMENT_TYPE = (
        ("file", "File"),
        ("image", "Image"),
        ("audio", "Audio"),
    )

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="chat/attachments/")
    attachment_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
       

class UserBlock(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)
    blocked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("blocker", "blocked")
class MessageMention(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="mentions")
    mentioned_user = models.ForeignKey(User, on_delete=models.CASCADE)
    seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("message", "mentioned_user")
        indexes = [models.Index(fields=["mentioned_user", "seen_at"])]


class MessageReaction(models.Model):
    REACTION = (("like", "Like"), ("dislike", "Dislike"))

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reaction = models.CharField(max_length=10, choices=REACTION)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")


class AiFeedback(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    reaction = models.CharField(max_length=10, choices=(("like", "Like"), ("dislike", "Dislike")))
    role = models.CharField(max_length=20)
    knowledge_level = models.PositiveSmallIntegerField(default=0)
    room_type = models.CharField(max_length=10)
    clinic_id = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)