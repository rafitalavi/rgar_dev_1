from django.db import transaction
from django.utils import timezone
from notifications.models import Notification
from accounts.models import User
from chat.models import UserBlock
from .models import Message, MessageMention, ChatParticipant, RoomUserState
from accounts.models import User
from channels.db import database_sync_to_async
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


# def mark_room_read_and_clear_mentions(*, room_id: int, user, last_message_id: int):
#     # 🔹 update room read state
#     st, _ = RoomUserState.objects.get_or_create(
#         room_id=room_id,
#         user=user
#     )
#     st.last_read_message_id = last_message_id
#     st.save(update_fields=["last_read_message_id"])

#     # 🔹 find unread mentions that were actually read
#     mentions_qs = MessageMention.objects.filter(
#         mentioned_user=user,
#         message__room_id=room_id,
#         message_id__lte=last_message_id,
#         seen_at__isnull=True
#     )

#     mention_message_ids = list(
#         mentions_qs.values_list("message_id", flat=True)
#     )

#     # 🔹 mark mentions as seen
#     mentions_qs.update(seen_at=timezone.now())

#     # 🔹 sync notifications (VERY IMPORTANT)
#     if mention_message_ids:
#         Notification.objects.filter(
#             user=user,
#             type="mention",
#             message_id__in=mention_message_ids,
#             is_seen=False
#         ).update(is_seen=True)
        


# def can_users_chat(user1: User, user2: User) -> bool:
#     # 🔒 system-level block
#     if user1.is_blocked or user2.is_blocked:
#         return False

#     # 🔒 personal block (either direction)
#     if UserBlock.objects.filter(
#         blocker=user1,
#         blocked=user2
#     ).exists():
#         return False

#     if UserBlock.objects.filter(
#         blocker=user2,
#         blocked=user1
#     ).exists():
#         return False

#     return True





def mark_room_read_and_clear_mentions(*, room_id: int, user, last_message_id: int):
    with transaction.atomic():
        st, _ = RoomUserState.objects.select_for_update().get_or_create(
            room_id=room_id,
            user=user
        )

        prev = st.last_read_message_id or 0
        effective = max(prev, last_message_id)

        if effective == prev:
            return

        st.last_read_message_id = effective
        st.save(update_fields=["last_read_message_id"])

        mentions_qs = MessageMention.objects.filter(
            mentioned_user=user,
            message__room_id=room_id,
            message_id__lte=effective,
            seen_at__isnull=True
        )

        mention_message_ids = list(
            mentions_qs.values_list("message_id", flat=True)
        )

        mentions_qs.update(seen_at=timezone.now())

        if mention_message_ids:
            Notification.objects.filter(
                user=user,
                notif_type="mention",
                is_seen=False,
                payload__message_id__in=mention_message_ids
            ).update(is_seen=True)




def mark_room_read_internal(*, room_id: int, user, last_message_id: int):
    from .models import RoomUserState, MessageMention
    from notifications.models import Notification
    from django.utils import timezone

    # 🔹 update read pointer
    state, _ = RoomUserState.objects.get_or_create(
        room_id=room_id,
        user=user
    )

    if state.last_read_message_id and state.last_read_message_id >= last_message_id:
        return  # already read

    state.last_read_message_id = last_message_id
    state.save(update_fields=["last_read_message_id"])

    # 🔹 clear mentions
    mentions = MessageMention.objects.filter(
        mentioned_user=user,
        message__room_id=room_id,
        message_id__lte=last_message_id,
        seen_at__isnull=True
    )

    mention_message_ids = list(
        mentions.values_list("message_id", flat=True)
    )

    mentions.update(seen_at=timezone.now())

    # 🔹 clear mention notifications
    if mention_message_ids:
        Notification.objects.filter(
            user=user,
            notif_type="mention",
            payload__message_id__in=mention_message_ids,
            is_seen=False
        ).update(is_seen=True)



# chat/services_messages.py

from django.db import transaction
from django.utils import timezone
from chat.models import RoomUserState, MessageMention
from notifications.models import Notification


def mark_room_read(
    *,
    room_id: int,
    user,
    last_message_id: int
):
    """
    Backend-authoritative read logic
    """
    with transaction.atomic():
        state, _ = RoomUserState.objects.select_for_update().get_or_create(
            room_id=room_id,
            user=user
        )

        prev = state.last_read_message_id or 0
        effective = max(prev, last_message_id)

        if effective == prev:
            return False  # nothing changed

        state.last_read_message_id = effective
        state.save(update_fields=["last_read_message_id"])

        # 🔹 clear mentions
        mentions = MessageMention.objects.filter(
            mentioned_user=user,
            message__room_id=room_id,
            message_id__lte=effective,
            seen_at__isnull=True
        )

        mention_ids = list(
            mentions.values_list("message_id", flat=True)
        )

        mentions.update(seen_at=timezone.now())

        # 🔹 clear notifications
        if mention_ids:
            Notification.objects.filter(
                user=user,
                notif_type="mention",
                is_seen=False,
                payload__message_id__in=mention_ids
            ).update(is_seen=True)

        return True
