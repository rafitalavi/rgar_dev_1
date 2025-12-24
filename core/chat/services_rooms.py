from django.db import transaction
from medical.models import ClinicUser, Clinic
from .models import ChatRoom, ChatParticipant, RoomUserState, UserBlock

@transaction.atomic
def ensure_clinic_group_room(clinic: Clinic) -> ChatRoom:
    room, _ = ChatRoom.objects.get_or_create(room_type="group", clinic=clinic, name=f"{clinic.name} - All Staff")
    user_ids = list(ClinicUser.objects.filter(clinic=clinic).values_list("user_id", flat=True))

    ChatParticipant.objects.bulk_create([ChatParticipant(room=room, user_id=u) for u in user_ids], ignore_conflicts=True)
    RoomUserState.objects.bulk_create([RoomUserState(room=room, user_id=u) for u in user_ids], ignore_conflicts=True)
    return room

@transaction.atomic
def get_or_create_private_room(user_id: int, other_id: int) -> ChatRoom:
    if UserBlock.objects.filter(blocker_id=user_id, blocked_id=other_id).exists() or \
       UserBlock.objects.filter(blocker_id=other_id, blocked_id=user_id).exists():
        raise PermissionError("Chat not allowed (blocked).")

    a, b = sorted([user_id, other_id])
    key = f"private:{a}:{b}"

    room = ChatRoom.objects.filter(room_type="private", unique_key=key).first()
    if room:
        return room

    room = ChatRoom.objects.create(room_type="private", unique_key=key)
    ChatParticipant.objects.bulk_create([ChatParticipant(room=room, user_id=a), ChatParticipant(room=room, user_id=b)])
    RoomUserState.objects.bulk_create([RoomUserState(room=room, user_id=a), RoomUserState(room=room, user_id=b)])
    return room


# @transaction.atomic
# def get_or_create_private_room(user_id: int, other_id: int) -> ChatRoom:
#     # 🔒 Block check
#     if UserBlock.objects.filter(
#         blocker_id=user_id, blocked_id=other_id
#     ).exists() or UserBlock.objects.filter(
#         blocker_id=other_id, blocked_id=user_id
#     ).exists():
#         raise PermissionError("Chat not allowed (blocked).")

#     a, b = sorted([user_id, other_id])
#     key = f"private:{a}:{b}"

#     # ✅ Atomic get_or_create
#     room, _ = ChatRoom.objects.get_or_create(
#         room_type="private",
#         unique_key=key,
#         defaults={"name": ""}
#     )

#     # ✅ Participants (safe)
#     ChatParticipant.objects.get_or_create(room=room, user_id=a)
#     ChatParticipant.objects.get_or_create(room=room, user_id=b)

#     # ✅ User states (CRITICAL)
#     RoomUserState.objects.get_or_create(
#         room=room,
#         user_id=a,
#         defaults={"is_deleted": False}
#     )
#     RoomUserState.objects.get_or_create(
#         room=room,
#         user_id=b,
#         defaults={"is_deleted": False}
#     )

#     return room



@transaction.atomic
def get_or_create_ai_room(user_id: int) -> ChatRoom:
    key = f"ai:{user_id}"
    room = ChatRoom.objects.filter(room_type="ai", unique_key=key).first()
    if room:
        return room
    room = ChatRoom.objects.create(room_type="ai", unique_key=key, name="AI Assistant")
    ChatParticipant.objects.create(room=room, user_id=user_id)
    RoomUserState.objects.create(room=room, user_id=user_id)
    return room

@transaction.atomic
def create_custom_group(created_by, name: str, user_ids: list[int]) -> ChatRoom:
    room = ChatRoom.objects.create(room_type="group", name=name, created_by=created_by)
    ChatParticipant.objects.bulk_create([ChatParticipant(room=room, user_id=u) for u in user_ids], ignore_conflicts=True)
    RoomUserState.objects.bulk_create([RoomUserState(room=room, user_id=u) for u in user_ids], ignore_conflicts=True)
    return room
