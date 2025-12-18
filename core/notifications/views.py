from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions_app.services import has_permission
from .models import Notification

class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_permission(request.user, "notif:view"):
            return Response({"detail":"Forbidden"}, status=403)
        qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:50]
        return Response(list(qs.values("id","notif_type","title","payload","is_seen","created_at")))

class NotificationMarkSeenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notif_id):
        if not has_permission(request.user, "notif:mark_seen"):
            return Response({"detail":"Forbidden"}, status=403)
        Notification.objects.filter(id=notif_id, user=request.user).update(is_seen=True)
        return Response({"success": True})
