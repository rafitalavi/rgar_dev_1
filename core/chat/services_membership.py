from chat.models import ChatRoom, ChatParticipant, RoomUserState

def auto_join_clinic_groups_for_user(user, clinic):
    rooms = ChatRoom.objects.filter(
        room_type="group",
        clinic=clinic
    )
    print("AUTO JOIN:", user.id, clinic.id)
    for room in rooms:
        join = False

        if room.group_kind == "clinic_all":
            join = True
        elif room.group_kind == "clinic_role" and room.role == user.role:
            join = True

        if not join:
            continue

        ChatParticipant.objects.get_or_create(
            room=room,
            user=user
        )

        RoomUserState.objects.get_or_create(
            room=room,
            user=user
        )
