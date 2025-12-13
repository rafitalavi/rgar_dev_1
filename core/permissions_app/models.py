from django.db import models

# Create your models here.
from django.db import models

class Permission(models.Model):
    code = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.code

class RolePermission(models.Model):
    role = models.CharField(max_length=20)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "permission")

class UserPermission(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("user", "permission")