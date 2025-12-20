from django.db import models
from django.utils.translation import gettext_lazy as _

from django.db.models import Q

class Clinic(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=256, blank=True, null=True)
    phone_number = models.CharField(max_length=16, blank=True, null=True)
    fax_number = models.CharField(max_length=250, blank=True, null=True)
    website = models.CharField(max_length=256, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Clinic")
        verbose_name_plural = _("Clinics")
        ordering = ["name"]

        # ✅ UNIQUE ONLY WHEN NOT DELETED
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_deleted=False),
                name="unique_active_clinic_name"
            )
        ]

        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return self.name




class ClinicUser(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "clinic")