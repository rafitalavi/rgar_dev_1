from celery import shared_task
from .models import Message, RoomUserState
from .services_ai import build_ai_prompt, generate_ai_reply

@shared_task
def group_ai_reply_if_no_human_response(message_id: int):
    try:
        msg = Message.objects.select_related("room","sender").get(id=message_id)
    except Message.DoesNotExist:
        return

    room = msg.room
    if room.room_type != "group":
        return

    # if everyone deleted room -> skip (production rule)
    if not RoomUserState.objects.filter(room=room, is_deleted=False).exists():
        return

    # if any human replied after msg -> skip
    if Message.objects.filter(room=room, id__gt=msg.id, is_ai=False).exists():
        return

    user = msg.sender
    if not user:
        return

    prompt = build_ai_prompt(user, msg.content)
    ai_text = generate_ai_reply(prompt)

    Message.objects.create(
        room=room,
        sender=None,
        is_ai=True,
        content=ai_text,
        parent_message=msg
    )
