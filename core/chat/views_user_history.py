# chat/views_user_history.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from permissions_app.services import has_permission
from accounts.models import User
from chat.models import ChatRoom, RoomUserState


class UserRoomHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        # permission check
        if not has_permission(request.user, "chat:view_user_history"):
            return Response({"detail": "Forbidden"}, status=403)

        try:
            target_user = User.objects.get(id=user_id, is_deleted=False)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # rooms where TARGET USER participates and NOT soft-deleted by them
        rooms = ChatRoom.objects.filter(
            participants__user=target_user,
            user_states__user=target_user,
            user_states__is_deleted=False
        ).distinct().order_by("-id")

        data = []
        for r in rooms:
            data.append({
                "room_id": r.id,
                "room_type": r.room_type,
                "clinic_id": r.clinic_id,
                "name": r.name,
            })

        return Response({
            "read_only": True,
            "target_user": {
                "id": target_user.id,
                "email": target_user.email,
                "role": target_user.role,
            },
            "results": data
        })
# chat/views_user_history.py
from chat.models import Message, RoomUserState
from chat.serializers import MessageSerializer


class UserMessageHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id, room_id):
        if not has_permission(request.user, "chat:view_user_history"):
            return Response({"detail": "Forbidden"}, status=403)

        try:
            target_user = User.objects.get(id=user_id, is_deleted=False)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        # ensure TARGET USER actually had access
        state = RoomUserState.objects.filter(
            room_id=room_id,
            user=target_user,
            is_deleted=False
        ).first()

        if not state:
            return Response({"detail": "Chat not available"}, status=404)

        qs = Message.objects.filter(
            room_id=room_id
        ).select_related(
            "sender"
        ).prefetch_related(
            "attachments",
            "reactions",
            "mentions"
        ).order_by("-id")[:100]

        return Response({
            "read_only": True,
            "target_user": {
                "id": target_user.id,
                "email": target_user.email,
                "role": target_user.role,
            },
            "results": MessageSerializer(
                qs,
                many=True,
                context={"request": request}
            ).data
        })
