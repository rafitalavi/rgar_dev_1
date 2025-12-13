from accounts.models import User
from .models import ClinicUser

def delete_clinic_and_users(clinic):
    clinic.is_deleted = True
    clinic.save(update_fields=["is_deleted"])

    user_ids = ClinicUser.objects.filter(clinic=clinic).values_list("user_id", flat=True)
    User.objects.filter(id__in=list(user_ids)).update(is_deleted=True, is_active=False)