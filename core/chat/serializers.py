from rest_framework import serializers
from .models import Message ,ChatRoom
from medical.models import ClinicUser
from accounts.models import User

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "room_id",
            "content",
            "is_ai",
            "created_at",
            "parent_message_id",
            "sender",
            "attachments",
            "reactions",
            "my_reaction",
        )

    def get_sender(self, obj):
        if not obj.sender:
            return None
        u = obj.sender
        return {
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}".strip() or u.email,
            "role": u.role,
        }

    def get_attachments(self, obj):
        return [
            {
                "id": a.id,
                "url": a.file.url,
                "type": a.attachment_type,
            }
            for a in obj.attachments.all()
        ]

    def get_reactions(self, obj):
        likes = obj.reactions.filter(reaction="like").select_related("user")
        dislikes = obj.reactions.filter(reaction="dislike").select_related("user")

        return {
            "like": {
                "count": likes.count(),
                "users": [
                    {
                        "id": r.user.id,
                        "name": f"{r.user.first_name} {r.user.last_name}".strip()
                                or r.user.email,
                        "role": r.user.role,
                    }
                    for r in likes
                ],
            },
            "dislike": {
                "count": dislikes.count(),
                "users": [
                    {
                        "id": r.user.id,
                        "name": f"{r.user.first_name} {r.user.last_name}".strip()
                                or r.user.email,
                        "role": r.user.role,
                    }
                    for r in dislikes
                ],
            },
        }

    def get_my_reaction(self, obj):
        req = self.context.get("request")
        if not req or req.user.is_anonymous:
            return None

        r = obj.reactions.filter(user=req.user).first()
        return r.reaction if r else None




class CreateClinicGroupSerializer(serializers.Serializer):
    clinic_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200)
    group_kind = serializers.ChoiceField(
        choices=["clinic_all", "clinic_role", "clinic_custom"]
    )
    role = serializers.CharField(required=False, allow_null=True)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    def validate(self, attrs):
        clinic_id = attrs["clinic_id"]
        group_kind = attrs["group_kind"]
        role = attrs.get("role")
        user_ids = attrs.get("user_ids", [])

        # clinic_role validation
        if group_kind == "clinic_role" and not role:
            raise serializers.ValidationError(
                {"role": "role is required for clinic_role"}
            )
        if group_kind == "clinic_all":
            exists = ChatRoom.objects.filter(
            room_type="group",
            clinic_id=clinic_id,
            group_kind="clinic_all"
        ).exists()

            if exists:
                raise serializers.ValidationError({
                "group_kind": {
                    "code": "CLINIC_ALL_EXISTS",
                    "message": "Clinic-wide group already exists for this clinic"
                }
            })
        # clinic_custom validation
        if group_kind == "clinic_custom":
            if not user_ids:
                raise serializers.ValidationError(
                    {"code": "CLINIC_ALL_EXISTS",
                "message": "At least one user needed"}
                )

            #  CORE RULE: all users must belong to same clinic
            clinic_users = set(
                ClinicUser.objects.filter(
                    clinic_id=clinic_id,
                    user_id__in=user_ids
                ).values_list("user_id", flat=True)
            )

            if clinic_users != set(user_ids):
                raise serializers.ValidationError(
                    {
                        "user_ids":{
                "code": "CLINIC_ALL_EXISTS",
                "message": "All selected users must belong to the same clinic"
            }
                    }
                )

        return attrs
    
# chat/serializers.py
class DirectMessageCreateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    content = serializers.CharField(allow_blank=False)

    def validate_user_ids(self, values):
        if len(set(values)) != len(values):
            raise  serializers.ValidationError({
            "code": "DUPLICATE_USERS",
            "message": "Duplicate users are not allowed"
        })


        qs = User.objects.filter(
            id__in=values,
            is_active=True,
            is_deleted=False,
            is_blocked=False
        )

        if qs.count() != len(values):
            raise serializers.ValidationError("One or more users are invalid")

        return values

#add member
class AddGroupMembersSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

    def validate_user_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "Duplicate user IDs are not allowed"
            )
        return value
    
    
# block members
class BlockGroupMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()

    def validate_user_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("Invalid user id")
        return value

#block user
# chat
class BlockUnblockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["block", "unblock"])

    def validate_user_id(self, value):
        from accounts.models import User

        if not User.objects.filter(
            id=value,
            is_active=True,
            is_deleted=False
        ).exists():
            raise serializers.ValidationError("User not found")
        return value




class BlockGroupMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["block", "unblock"])




from .models import MessageReaction

class ReactionListSerializer(serializers.ModelSerializer):
    message_id = serializers.IntegerField(source="message.id")
    message = serializers.CharField(source="message.content")
    room_id = serializers.IntegerField(source="message.room_id")
    clinic_id = serializers.IntegerField(source="message.room.clinic_id")
    reacted_by = serializers.SerializerMethodField()
    reacted_at = serializers.DateTimeField(source="created_at")

    class Meta:
        model = MessageReaction
        fields = (
            "message_id",
            "message",
            "reaction",
            "room_id",
            "clinic_id",
            "reacted_by",
            "reacted_at",
        )

    def get_reacted_by(self, obj):
        user = obj.user
        return {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "role": user.role,
        }