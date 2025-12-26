from django.core.management.base import BaseCommand
from permissions_app.models import Permission, RolePermission

PERMS = [
    # User Permissions
    ("user:create", "Create user"),
    ("user:view", "View user"),
    ("user:update", "Update user"),
    ("user:delete", "Delete user"),
    ("listUser:view", "View users"),
    ("user:statusupdate", "user Status update"),
    # Clinic Permissions
    ("clinic:create", "Create clinic"),
    ("clinic:view", "View clinics"),
    ("clinic:update", "Update clinic"),
    ("clinic:delete", "Delete clinic"),
    
    # Subject Permissions
    ("subject:create", "Create subject"),
    ("subject:view", "View subjects"),
    ("subject:update", "Update subject"),
    ("subject:delete", "Delete subject"),
    
    # Chat Permissions
    ("chat:view_all_users", "View all chat users"),
    ("chat:view_all_history", "View all chat history"),
    ("chat:create_private", "Create private chat"),
    ("chat:create_group", "Create group chat"),
    ("chat:send", "Send messages"),
    ("chat:block_user", "Block users in chat"),
    ("chat:delete_chat", "Delete chat"),
    ("chat:use_ai", "Use AI in chat"),
    ("chat:ai_group_autoreply", "AI group auto-reply"),
    ("chat:react_like", "React with like"),
    ("chat:react_dislike", "React with dislike"),
    ("chat:impersonate","Chat Impersonate"),
    # Notification Permissions
    ("notif:view", "View notifications"),
    ("notif:mark_seen", "Mark notifications as seen"),
    #assesments 
    ("assessment:create" , "Assesments Create"),
    ("assessment:view_all" , "Assesments Qeustionview"),
    ("assessment:update" , "Assesments update"),
    
    
]

ROLE_MATRIX = {
    "owner": [p[0] for p in PERMS],

    "president": [
        "listUser:view",
        "user:create","user:view","user:update",
        "clinic:view","clinic:update",
        "chat:create_group","chat:create_private",
        "chat:send","chat:block_user","chat:use_ai",
        "chat:delete_chat","chat:ai_group_autoreply",
        "chat:react_dislike","chat:block_user",
        "notif:view","notif:mark_seen","chat:impersonate",
        "chat:view_all_history","chat:view_all_users",
        "assessment:create","assessment:view_all",
        "assessment:update", 
    ],

    "manager": [
        "user:view","clinic:view","clinic:update",
        "chat:create_private","chat:send",
        "chat:block_user","chat:use_ai",
        "chat:delete_chat","chat:ai_group_autoreply",
        "notif:view","notif:mark_seen",
        # "chat:view_all_history",
    ],

    "doctor": [
        "user:view",
        "clinic:view","chat:create_private","chat:send",
        "chat:block_user","chat:use_ai",
        "chat:delete_chat","chat:ai_group_autoreply",
        "notif:view","notif:mark_seen",
        # "chat:view_all_history",
    ],

    "staff": [
        "user:view",
        "clinic:view","chat:create_private","chat:send",
        "chat:block_user","chat:use_ai",
        "chat:delete_chat","chat:ai_group_autoreply",
        "notif:view","notif:mark_seen",
        # "chat:view_all_history",
    ],

    "jr_staff": [
        "user:view",
        "clinic:view","chat:create_private","chat:send",
        "chat:block_user","chat:use_ai",
        "chat:delete_chat","chat:ai_group_autoreply",
        "notif:view","notif:mark_seen",
        # "chat:view_all_history",
    ],
}

# "user:view",
# class Command(BaseCommand):
#     def handle(self, *args, **kwargs):
#         perm_objs = {}
#         for code, _desc in PERMS:
#             perm, _ = Permission.objects.get_or_create(code=code)
#             perm_objs[code] = perm

#         RolePermission.objects.all().delete()
#         for role, codes in ROLE_MATRIX.items():
#             for code in codes:
#                 RolePermission.objects.create(role=role, permission=perm_objs[code])

#         self.stdout.write(self.style.SUCCESS("Seeded permissions successfully"))

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        perm_objs = {}

        # 1️⃣ Create permissions
        for code, _desc in PERMS:
            perm, _ = Permission.objects.get_or_create(code=code)
            perm_objs[code] = perm

        # 2️⃣ Sync role permissions
        for role, codes in ROLE_MATRIX.items():
            desired_perms = set(codes)

            existing = RolePermission.objects.filter(role=role)
            existing_codes = set(
                existing.values_list("permission__code", flat=True)
            )

            # ➕ Add missing
            for code in desired_perms - existing_codes:
                RolePermission.objects.create(
                    role=role,
                    permission=perm_objs[code]
                )

            # ➖ Remove extra
            for code in existing_codes - desired_perms:
                RolePermission.objects.filter(
                    role=role,
                    permission__code=code
                ).delete()

        self.stdout.write(
            self.style.SUCCESS("Role permissions synced successfully")
        )
