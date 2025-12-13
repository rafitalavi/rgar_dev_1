from django.core.management.base import BaseCommand
from permissions_app.models import Permission, RolePermission

PERMS = [
    # User Permission
    ("user:create", "Create user"),
    ("user:view", "View users"),
    ("user:update", "Update user"),
    ("user:delete", "Delete user"),
      # Clinics permissions  
    ("clinic:create", "Create clinic"),
    ("clinic:view", "View clinics"),
    ("clinic:update", "Update clinic"),
    ("clinic:delete", "Delete clinic"),
    
      # Subject permissions 
    ("subject:create", "Create subject"),
    ("subject:view", "View subjects"),
    ("subject:update", "Update subject"),
    ("subject:delete", "Delete subject"),
]

ROLE_MATRIX = {
    "owner": [p[0] for p in PERMS],
    "president": ["user:create","user:view","user:update", "clinic:create","clinic:view","clinic:update"],
    "manager": ["user:view", "clinic:view", "clinic:update"],
    "doctor": ["user:view", "clinic:view"],
    "staff": ["clinic:view"],
    "jr_staff": ["clinic:view"],
}

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        perm_objs = {}
        for code, _desc in PERMS:
            perm, _ = Permission.objects.get_or_create(code=code)
            perm_objs[code] = perm

        RolePermission.objects.all().delete()
        for role, codes in ROLE_MATRIX.items():
            for code in codes:
                RolePermission.objects.create(role=role, permission=perm_objs[code])

        self.stdout.write(self.style.SUCCESS("Seeded permissions successfully"))