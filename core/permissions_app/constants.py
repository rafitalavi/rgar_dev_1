# permissions_app/constants.py

PERMISSION_GROUPS = {
    "user_management": {
        "label": "User Management",
        "permissions": [
            "user:create",
            "user:view",
            "user:update",
            "user:delete",
            "listUser:view",
               "user:statusupdate",
            
        ],
    },

    "clinic_management": {
        "label": "Clinic Management",
        "permissions": [
            "clinic:create",
            "clinic:view",
            "clinic:update",
            "clinic:delete",
        ],
    },

    "chat": {
        "label": "Chat",
        "permissions": [
            "chat:view_all_users",
            "chat:view_all_history",
            "chat:create_private",
            "chat:create_group",
            "chat:send",
            "chat:block_user",
            "chat:delete_chat",
            "chat:use_ai",
            "chat:ai_group_autoreply",
        ],
    },

    "notifications": {
        "label": "Notifications",
        "permissions": [
            "notif:view",
            "notif:mark_seen",
        ],
    },
}
