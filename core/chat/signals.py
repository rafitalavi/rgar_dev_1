from django.db.models.signals import post_save ,post_delete ,pre_save
from django.dispatch import receiver
from medical.models import ClinicUser
from .services_membership import auto_join_clinic_groups_for_user
from chat.models import ChatParticipant, RoomUserState, ChatRoom
from accounts.models import User
@receiver(post_save, sender=ClinicUser)
def on_clinic_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    auto_join_clinic_groups_for_user(instance.user, instance.clinic)



# @receiver(post_delete, sender=ClinicUser)
# def remove_user_from_clinic_groups(sender, instance, **kwargs):
#     user = instance.user
#     clinic = instance.clinic

#     rooms = ChatRoom.objects.filter(
#         room_type="group",
#         clinic=clinic
#     )

#     ChatParticipant.objects.filter(
#         room__in=rooms,
#         user=user
#     ).delete()

#     RoomUserState.objects.filter(
#         room__in=rooms,
#         user=user
#     ).delete()
    
    
@receiver(pre_save, sender=User)
def sync_role_groups_on_role_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    old = User.objects.get(pk=instance.pk)
    if old.role == instance.role:
        return

    clinics = ClinicUser.objects.filter(user=instance).values_list("clinic", flat=True)

    for clinic_id in clinics:
        rooms = ChatRoom.objects.filter(
            room_type="group",
            clinic_id=clinic_id,
            group_kind="clinic_role"
        )

        # 🔻 remove from old role rooms
        ChatParticipant.objects.filter(
            room__in=rooms.filter(role=old.role),
            user=instance
        ).delete()

        RoomUserState.objects.filter(
            room__in=rooms.filter(role=old.role),
            user=instance
        ).delete()

        # 🔺 add to new role rooms
        for room in rooms.filter(role=instance.role):
            ChatParticipant.objects.get_or_create(
                room=room,
                user=instance
            )
            RoomUserState.objects.get_or_create(
                room=room,
                user=instance
            )