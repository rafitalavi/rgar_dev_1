from .models import ChatParticipant, RoomUserState

def ensure_room_access(user, room_id: int) -> bool:
    if not ChatParticipant.objects.filter(room_id=room_id, user=user).exists():
        return False
    if not RoomUserState.objects.filter(room_id=room_id, user=user, is_blocked=False).exists():
        return False
    return True
