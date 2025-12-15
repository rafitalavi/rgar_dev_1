from .models import RolePermission, UserPermission

from medical.models import ClinicUser
from accounts.models import User


def has_permission(user, code):
    if not user or not user.is_authenticated:
        return False

    # Owner or superuser: always allowed
    if user.is_superuser or user.role == "owner":
        return True

    if UserPermission.objects.filter(user=user, permission__code=code).exists():
        return True

    return RolePermission.objects.filter(
        role=user.role, permission__code=code
    ).exists()



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
