# chat/tasks.py

from celery import shared_task
from django.db import transaction
from notifications.models import Notification
from accounts.models import User
from chat.models import Message, MessageAttachment, AiFeedback
from chat.services_ai_moderation import ai_analyze_message
from chat.services_ai import get_reply, send_ai_message

@shared_task
def ai_observe_group_message(message_id: int):
    msg = Message.objects.select_related("room", "sender").filter(id=message_id).first()
    if not msg:
        return

    if msg.is_ai or msg.room.room_type != "group":
        return
    if msg.is_deleted or msg.room.is_deleted:
        return

    # AI analyzes text + attachments (AI extracts itself)
    result = ai_analyze_message(msg)
    if not result.get("flagged"):
        return

    if AiFeedback.objects.filter(message=msg).exists():
        return

    with transaction.atomic():
        AiFeedback.objects.create(
            message=msg,
            reaction="dislike",
            role=msg.sender.role if msg.sender else "",
            room_type="group",
            clinic_id=msg.room.clinic_id,
        )

    presidents = User.objects.filter(
        role__in=["president", "owner"],
        is_active=True,
        is_deleted=False,
        is_blocked=False,
    )

    Notification.objects.bulk_create([
        Notification(
            user=p,
            type="AI_ALERT",
            payload={
                "message_id": msg.id,
                "room_id": msg.room_id,
                "clinic_id": msg.room.clinic_id,
                "reason": result.get("reason", ""),
            }
        )
        for p in presidents
    ])



@shared_task
def group_ai_reply_if_no_human_response(message_id: int):
    msg = Message.objects.select_related("room").filter(id=message_id).first()
    if not msg:
        return

    room = msg.room
    if room.room_type != "group":
        return

    # cancel if any human replied
    if Message.objects.filter(
        room=room,
        created_at__gt=msg.created_at,
        is_ai=False
    ).exclude(sender__role="ai").exists():
        return

    # cancel if AI already replied
    if Message.objects.filter(
        room=room,
        created_at__gt=msg.created_at,
        is_ai=True
    ).exists():
        return

    has_attachments = MessageAttachment.objects.filter(message=msg).exists()

    ai_text = get_reply(
        msg.content,
        has_attachments=has_attachments
    )

    if not ai_text:
        return

    send_ai_message(room=room, content=ai_text)