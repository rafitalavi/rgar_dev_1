from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from chat.models import Message


# def serialize_message_payload(message: Message):
#     sender = None
#     if message.sender:
#         sender = {
#             "id": message.sender.id,
#             "name": f"{message.sender.first_name} {message.sender.last_name}".strip(),
#             "role": message.sender.role,
#         }

#     return {
#         "id": message.id,
#         "room_id": message.room_id,
#         "content": message.content,
#         "is_ai": message.is_ai,
#         "created_at": message.created_at.isoformat(),
#         "sender": sender,
#         "parent_message_id": message.parent_message_id,
        
#     }
def serialize_message_payload(message):
    return {
        "id": message.id,
        "room_id": message.room_id,
        "content": message.content,
        "is_ai": message.is_ai,
        "created_at": message.created_at.isoformat(),
        "sender": {
            "id": message.sender_id,
            "name": f"{message.sender.first_name} {message.sender.last_name}".strip(),
            "role": message.sender.role,
        } if message.sender else None,
        "attachments": [
            {
                "id": a.id,
                "url": a.file.url,
                "type": a.attachment_type,
            }
            for a in message.attachments.all()
        ],
    }


def broadcast_message(message: Message):
    """
    Send new message to room WS
    """
    channel_layer = get_channel_layer()
    payload = serialize_message_payload(message)

    async_to_sync(channel_layer.group_send)(
        f"room_{message.room_id}",
        {
            "type": "message_event",
            "message": payload,
        }
    )
