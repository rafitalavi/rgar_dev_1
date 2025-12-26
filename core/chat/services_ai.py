from django.db import transaction
from chat.models import ChatRoom, Message
from chat.services_messages import create_message_with_mentions
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.realtime import serialize_message_payload
from accounts.models import User


@transaction.atomic
def send_ai_message(
    *,
    room: ChatRoom,
    content: str,
):
    """
    Internal-only AI message sender.
    NO authentication required.
    """

    ai_user = User.objects.filter(
        role="ai",
        is_active=True,
        is_deleted=False
    ).first()

    if not ai_user:
        raise RuntimeError("AI user not configured")

    # 🔒 Ensure AI is participant
    if not room.participants.filter(user=ai_user).exists():
        raise PermissionError("AI is not a member of this room")

    # ✅ Create message
    msg = create_message_with_mentions(
        room=room,
        sender=ai_user,
        content=content,
        mention_user_ids=[]
    )

    
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"room_{room.id}",
        {
            "type": "message_event",
            "message": serialize_message_payload(msg),
        }
    )

    return msg


# chat/services_ai.py

def get_reply(user_message: str | None, *, has_attachments: bool = False) -> str:
    """
    Temporary AI logic.
    Replace later with OpenAI / LLM.
    """

    text = (user_message or "").lower().strip()

    # CASE 1: FILE-ONLY MESSAGE
    if not text and has_attachments:
        return "I’ve received the file 📎. What would you like me to do with it?"

    # CASE 2: Greeting
    if text in ("hi", "hello", "hey"):
        return "Hello 👋 How can I help you today?"

    # ✅ CASE 3: Asking for help
    if "help" in text:
        return "Sure 🙂 Tell me what you need help with."

    # ✅ CASE 4: Empty message, no file
    if not text:
        return ""

    # ✅ CASE 5: Default
    return "I’m here 🤖 Please tell me more."



# def build_ai_prompt(user, message_text: str) -> str:
#     # your role-based behavior comes from DB (user.role)
#     return f"You are an assistant for role={user.role}, level={getattr(user,'knowledge_level',0)}. Message: {message_text}"

# def generate_ai_reply(prompt: str) -> str:
#     # Replace later with OpenAI/local LLM call
#     return f"(AI) {prompt[:180]}"
