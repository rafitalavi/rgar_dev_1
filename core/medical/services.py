from accounts.models import User
from .models import ClinicUser

def delete_clinic_and_users(clinic):
    # Soft delete clinic
    clinic.is_deleted = True
    clinic.save(update_fields=["is_deleted"])

    # Get users linked to this clinic
    user_ids = ClinicUser.objects.filter(
        clinic=clinic
    ).values_list("user_id", flat=True)

    # Soft delete users EXCEPT owner & president
    User.objects.filter(
        id__in=user_ids
    ).exclude(
        role__in=["owner", "president"]
    ).update(
        is_deleted=True,
        is_active=False
    )
