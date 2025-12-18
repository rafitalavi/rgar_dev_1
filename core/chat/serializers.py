from rest_framework import serializers
from .models import Message

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
