from accounts.models import User
from .models import ClinicUser



# good okkay
# def delete_clinic_and_users(clinic):
#     # Soft delete clinic
#     clinic.is_deleted = True
#     clinic.save(update_fields=["is_deleted"])

#     # Get users linked to this clinic
#     user_ids = ClinicUser.objects.filter(
#         clinic=clinic
#     ).values_list("user_id", flat=True)

#     # Soft delete users EXCEPT owner & president
#     User.objects.filter(
#         id__in=user_ids
#     ).exclude(
#         role__in=["owner", "president"]
#     ).update(
#         is_deleted=True,
#         is_active=False
#     )


def delete_clinic_and_users(clinic):
    # 1️⃣ Soft delete clinic
    clinic.is_deleted = True
    clinic.save(update_fields=["is_deleted"])

    # 2️⃣ Get users linked to this clinic
    users = User.objects.filter(
        clinicuser__clinic=clinic,
        is_deleted=False
    ).distinct()

    for user in users:
        # 3️⃣ Skip owner & president
        if user.role in ["owner", "president"]:
            continue

        # 4️⃣ Check if user belongs to OTHER active clinics
        has_other_clinics = ClinicUser.objects.filter(
            user=user
        ).exclude(
            clinic=clinic
        ).exclude(
            clinic__is_deleted=True
        ).exists()

        # 5️⃣ Deactivate only if no other clinics
        if not has_other_clinics:
            user.is_deleted = True
            user.is_active = False
            user.save(update_fields=["is_deleted", "is_active"])
