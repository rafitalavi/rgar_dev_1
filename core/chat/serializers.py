from rest_framework import serializers
from .models import Message ,ChatRoom
from medical.models import ClinicUser
class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ("id","room_id","content","is_ai","created_at","parent_message_id","sender","attachments","reactions","my_reaction")

    def get_sender(self, obj):
        if not obj.sender:
            return None
        u = obj.sender
        return {"id": u.id, "name": f"{u.first_name} {u.last_name}".strip(), "role": u.role}

    def get_attachments(self, obj):
        return [{"id": a.id, "url": a.file.url, "type": a.attachment_type} for a in obj.attachments.all()]

    def get_reactions(self, obj):
        return {
            "like": obj.reactions.filter(reaction="like").count(),
            "dislike": obj.reactions.filter(reaction="dislike").count(),
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