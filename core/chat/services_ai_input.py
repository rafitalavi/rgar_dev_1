from chat.models import MessageAttachment

def build_ai_input(message):
    attachments = MessageAttachment.objects.filter(message=message)

    return {
        "message_id": message.id,
        "room_id": message.room_id,
        "text": message.content or "",
        "room_type": message.room.room_type,
        "clinic_id": message.room.clinic_id,
        "sender_role": message.sender.role if message.sender else None,
        "attachments": [
            {
                "type": a.attachment_type,
                "url": a.file.url,
                "name": a.file.name,
            }
            for a in attachments
        ],
    }