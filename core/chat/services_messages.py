from django.db import transaction
from django.utils import timezone
from notifications.models import Notification
from .models import Message, MessageMention, ChatParticipant, RoomUserState
from accounts.models import User

@transaction.atomic
def create_message_with_mentions(room, sender, content: str, mention_user_ids: list[int]) -> Message:
    msg = Message.objects.create(room=room, sender=sender, content=content)

    mention_user_ids = list({int(x) for x in (mention_user_ids or []) if str(x).isdigit()})
    if not mention_user_ids:
        return msg

    # only participants can be mentioned
    allowed = set(ChatParticipant.objects.filter(room=room, user_id__in=mention_user_ids)
                  .values_list("user_id", flat=True))

    for uid in allowed:
        MessageMention.objects.get_or_create(message=msg, mentioned_user_id=uid)

        # don't notify if user soft-deleted this room
        if not RoomUserState.objects.filter(room=room, user_id=uid, is_deleted=False).exists():
            continue

        u = User.objects.get(id=uid)
        if not getattr(u, "notify_tagged_messages", True):
            continue

        Notification.objects.create(
            user_id=uid,
            notif_type="mention",
            title="You were mentioned",
            payload={"room_id": room.id, "message_id": msg.id},
        )

    return msg

# def mark_room_read_and_clear_mentions(room_id: int, user, last_message_id: int):
#     from .models import RoomUserState, MessageMention
#     st, _ = RoomUserState.objects.get_or_create(room_id=room_id, user=user)
#     st.last_read_message_id = last_message_id
#     st.save(update_fields=["last_read_message_id"])

#     MessageMention.objects.filter(
#         mentioned_user=user,
#         message__room_id=room_id,
#         message_id__lte=last_message_id,
#         seen_at__isnull=True
#     ).update(seen_at=timezone.now())


def mark_room_read_and_clear_mentions(*, room_id: int, user, last_message_id: int):
    # 🔹 update room read state
    st, _ = RoomUserState.objects.get_or_create(
        room_id=room_id,
        user=user
    )
    st.last_read_message_id = last_message_id
    st.save(update_fields=["last_read_message_id"])

    # 🔹 find unread mentions that were actually read
    mentions_qs = MessageMention.objects.filter(
        mentioned_user=user,
        message__room_id=room_id,
        message_id__lte=last_message_id,
        seen_at__isnull=True
    )

    mention_message_ids = list(
        mentions_qs.values_list("message_id", flat=True)
    )

    # 🔹 mark mentions as seen
    mentions_qs.update(seen_at=timezone.now())

    # 🔹 sync notifications (VERY IMPORTANT)
    if mention_message_ids:
        Notification.objects.filter(
            user=user,
            type="mention",
            message_id__in=mention_message_ids,
            is_seen=False
        ).update(is_seen=True)