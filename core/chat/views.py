from django.db.models import Max
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from chat.utils import get_effective_user
from rest_framework import status
from permissions_app.services import has_permission
from accounts.models import User
from medical.models import Clinic, ClinicUser
from django.utils import timezone
from django.db.models import Q
from .models import (
    ChatRoom, ChatParticipant, RoomUserState, UserBlock,
    Message, MessageAttachment, MessageReaction, AiFeedback
)

from django.db.models import Q
from .guards import ensure_room_access
from .serializers import MessageSerializer , CreateClinicGroupSerializer
from .services_rooms import ensure_clinic_group_room, get_or_create_private_room, get_or_create_ai_room, create_custom_group
from .services_messages import create_message_with_mentions, mark_room_read_and_clear_mentions
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.realtime import serialize_message_payload


# ---- USERS (picker) ----
class ChatUserPickerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = (request.GET.get("search") or "").strip()
        qs = User.objects.filter(is_deleted=False, is_active=True , is_blocked=False)

        if not (request.user.role == "owner" or has_permission(request.user, "chat:view_all_users")):
            clinic_ids = ClinicUser.objects.filter(user=request.user).values_list("clinic_id", flat=True)
            qs = qs.filter(clinicuser__clinic_id__in=list(clinic_ids)).distinct()

        if search:
            qs = qs.filter(email__icontains=search)

        return Response(list(qs.values("id","email","first_name","last_name","role")[:50]))

# ---- ROOMS LIST ----
# class RoomListView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         # special: owner/some roles can see ALL history read-only
#         if has_permission(request.user, "chat:view_all_history"):
#             rooms = ChatRoom.objects.all().order_by("-id")[:200]
#             return Response({
#                 "read_only": True,
#                 "results": [{"room_id": r.id, "type": r.room_type, "clinic_id": r.clinic_id, "name": r.name} for r in rooms]
#             })

#         rooms = ChatRoom.objects.filter(
#             participants__user=request.user,
#             user_states__user=request.user,
#             user_states__is_deleted=False
#         ).distinct().order_by("-id")[:200]

#         last_map = Message.objects.filter(room__in=rooms).values("room_id").annotate(last_id=Max("id"))
#         last_by_room = {x["room_id"]: x["last_id"] for x in last_map}

#         states = {s.room_id: s for s in RoomUserState.objects.filter(room__in=rooms, user=request.user)}
#         out = []
#         for r in rooms:
#             last_id = last_by_room.get(r.id)
#             last_read = states.get(r.id).last_read_message_id if states.get(r.id) else None
#             unread = bool(last_id and (last_read is None or last_id > last_read))
#             out.append({"room_id": r.id, "type": r.room_type, "clinic_id": r.clinic_id, "name": r.name, "unread": unread})

#         return Response({"read_only": False, "results": out})





class RoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 🔹 Owner / special roles: read-only access to all rooms
        if has_permission(request.user, "chat:view_all_history"):
            rooms = ChatRoom.objects.prefetch_related(
                "participants__user"
            ).order_by("-id")[:200]

            return Response({
                "read_only": True,
                "results": [
                    {
                        "room_id": r.id,
                        "type": r.room_type,
                        "clinic_id": r.clinic_id,
                        "name": r.name,
                        "member_count": r.participants.count(),
                        "members": [
                            {
                                "id": p.user.id,
                                "name": f"{p.user.first_name} {p.user.last_name}".strip(),
                                "role": p.user.role,
                            }
                            for p in r.participants.all()
                        ],
                    }
                    for r in rooms
                ]
            })

        # 🔹 Normal users: only their rooms
        rooms = ChatRoom.objects.filter(
            participants__user=request.user,
            user_states__user=request.user,
            user_states__is_deleted=False
        ).distinct().prefetch_related(
            "participants__user"
        ).order_by("-id")[:200]

        # 🔹 Get last message per room
        last_map = (
            Message.objects
            .filter(room__in=rooms)
            .values("room_id")
            .annotate(last_id=Max("id"))
        )
        last_by_room = {x["room_id"]: x["last_id"] for x in last_map}

        # 🔹 User states
        states = {
            s.room_id: s
            for s in RoomUserState.objects.filter(room__in=rooms, user=request.user)
        }

        out = []
        for r in rooms:
            last_id = last_by_room.get(r.id)
            state = states.get(r.id)
            last_read = state.last_read_message_id if state else None

            unread = bool(last_id and (last_read is None or last_id > last_read))

            out.append({
                "room_id": r.id,
                "type": r.room_type,
                "clinic_id": r.clinic_id,
                "name": r.name,
                "unread": unread,
                "member_count": r.participants.count(),
                "members": [
                    {
                        "id": p.user.id,
                        "name": f"{p.user.first_name} {p.user.last_name}".strip(),
                        "role": p.user.role,
                    }
                    for p in r.participants.all()
                ],
            })

        return Response({
            "read_only": False,
            "results": out
        })


# ---- CREATE PRIVATE ----
# class CreatePrivateRoomView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         if not has_permission(request.user, "chat:create_private"):
#             return Response({"detail":"Forbidden"}, status=403)

#         other_id = request.data.get("other_user_id")
        
#         if not other_id:
#             return Response({"detail":"other_user_id required"}, status=400)

#         try:
#             room = get_or_create_private_room(request.user.id, int(other_id))
#         except PermissionError as e:
#             return Response({"detail": str(e)}, status=403)

#         return Response({"room_id": room.id, "type":"private"}, status=201)


class CreatePrivateRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "chat:create_private"):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to create private chats"
                    }
                },
                status=403
            )

        other_id = request.data.get("other_user_id")
        if not other_id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "other_user_id required"
                    }
                },
                status=400
            )

        # 🔒 Global user block check (OWNER / ADMIN)
        if request.user.is_blocked:
            return Response(
                {
                    "success": False,
                    "is_blocked": True,
                    "blocked_user": "me",
                    "error": {
                        "code": "USER_BLOCKED",
                        "message": "Your account is blocked"
                    }
                },
                status=403
            )

        try:
            other_user = User.objects.get(id=int(other_id))
        except User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "User not found"
                    }
                },
                status=404
            )

        if other_user.is_blocked:
            return Response(
                {
                    "success": False,
                    "is_blocked": True,
                    "blocked_user": "other",
                    "error": {
                        "code": "USER_BLOCKED",
                        "message": "This user is blocked by admin"
                    }
                },
                status=403
            )

        try:
            room = get_or_create_private_room(request.user.id, other_user.id)
        except PermissionError as e:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ROOM_CREATION_DENIED",
                        "message": str(e)
                    }
                },
                status=403
            )

        return Response(
            {
                "success": True,
                "data": {
                    "room_id": room.id,
                    "type": "private",
                    "is_blocked": False
                }
            },
            status=201
        )



# ---- MY AI ROOM ----
class MyAiRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "chat:use_ai"):
            return Response({"detail":"Forbidden"}, status=403)
        room = get_or_create_ai_room(request.user.id)
        return Response({"room_id": room.id, "type":"ai"}, status=201)

# ---- ENSURE CLINIC GROUP ----
class EnsureClinicGroupRoomView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, clinic_id):
        if not has_permission(request.user, "clinic:view"):
            return Response({"detail":"Forbidden"}, status=403)

        clinic = Clinic.objects.get(id=clinic_id, is_deleted=False)
        room = ensure_clinic_group_room(clinic)
        return Response({"room_id": room.id, "type":"group"})

# ---- CREATE CUSTOM GROUP (selected users) ----

class CreateClinicGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 🔐 Permission
        if not has_permission(request.user, "chat:create_group"):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to create Group chats"
                    }
                },
                status=403
            )


        serializer = CreateClinicGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        clinic_id = data["clinic_id"]
        name = data["name"].strip()
        group_kind = data["group_kind"]
        role = data.get("role")
        user_ids = data.get("user_ids", [])

        # 🔐 Creator must belong to clinic (unless owner)
        if request.user.role != "owner":
            if not ClinicUser.objects.filter(
                clinic_id=clinic_id,
                user=request.user
            ).exists():
                return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "User must belong to a Clinic"
                    }
                },
                status=403
            )


        # 🔑 Unique key
        safe_name = "-".join(name.lower().split())
        if group_kind == "clinic_custom":
            ukey = f"clinic_custom:{clinic_id}:{safe_name}"
        else:
            ukey = f"clinic_custom:{clinic_id}:{group_kind}:{role or 'all'}:{safe_name}"

        room, created = ChatRoom.objects.get_or_create(
            unique_key=ukey,
            defaults={
                "room_type": "group",
                "clinic_id": clinic_id,
                "group_kind": group_kind,
                "role": role if group_kind == "clinic_role" else None,
                "name": name,
            }
        )

        # 🔹 Resolve members
        if group_kind == "clinic_all":
            qs = ClinicUser.objects.filter(clinic_id=clinic_id)

        elif group_kind == "clinic_role":
            qs = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                user__role=role
            )

        else:  # clinic_custom
            qs = ClinicUser.objects.filter(
                clinic_id=clinic_id,
                user_id__in=user_ids
            )

        # 🔹 Auto-add creator if missing
        if request.user.role != "owner":
            user_ids = set(qs.values_list("user_id", flat=True))
            if request.user.id not in user_ids:
                qs = ClinicUser.objects.filter(
                    clinic_id=clinic_id,
                    user_id__in=list(user_ids) + [request.user.id]
                )

        # 🔹 Create participants + state
        ChatParticipant.objects.bulk_create(
            [ChatParticipant(room=room, user=cu.user) for cu in qs],
            ignore_conflicts=True
        )

        RoomUserState.objects.bulk_create(
            [RoomUserState(room=room, user=cu.user) for cu in qs],
            ignore_conflicts=True
        )

        return Response(
            {
                "room_id": room.id,
                "type": "group",
                "group_kind": group_kind,
                "clinic_id": clinic_id,
                "created": created,
                "members": qs.count(),
            },
            status=201
        )



# class CreateClinicGroupView(APIView):
#     """
#     Creates a clinic-wise group:
#     - group_kind=clinic_all  -> all clinic members join
#     - group_kind=clinic_role -> only members of that role join
#     No manual user_ids selection.
#     """
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         if not has_permission(request.user, "chat:create_group"):
#             return Response({"message": ["Forbidden you don't have permissions"]}, status=403)
        
#         clinic_id = request.data.get("clinic_id")
#         name = (request.data.get("name") or "").strip()
#         group_kind = request.data.get("group_kind")  # clinic_all | clinic_role
#         role = request.data.get("role")              # required if clinic_role

#         if not clinic_id or not name or group_kind not in ("clinic_all", "clinic_role"):
#             return Response({"detail": "clinic_id, name, group_kind required"}, status=400)

#         if group_kind == "clinic_role" and not role:
#             return Response({"detail": "role required for clinic_role"}, status=400)

#         # creator must belong to clinic unless owner
#         if request.user.role != "owner":
#             if not ClinicUser.objects.filter(user=request.user, clinic_id=clinic_id).exists():
#                 return Response({"detail": "Forbidden"}, status=403)

#         # unique per clinic + kind + role + name to avoid duplicates
#         safe_name = "-".join(name.lower().split())
#         ukey = f"clinic_custom:{clinic_id}:{group_kind}:{role or 'all'}:{safe_name}"

#         room, created = ChatRoom.objects.get_or_create(
#             unique_key=ukey,
#             defaults={
#                 "room_type": "group",
#                 "clinic_id": clinic_id,
#                 "group_kind": group_kind,
#                 "role": role if group_kind == "clinic_role" else None,
#                 "name": name,
#             }
#         )

#         # auto-join existing clinic members by rule
#         qs = ClinicUser.objects.filter(clinic_id=clinic_id).select_related("user")

#         if group_kind == "clinic_role":
#             qs = qs.filter(user__role=role)

#         # create participant + state for each
#         ChatParticipant.objects.bulk_create(
#             [ChatParticipant(room=room, user=cu.user) for cu in qs],
#             ignore_conflicts=True
#         )
#         RoomUserState.objects.bulk_create(
#             [RoomUserState(room=room, user=cu.user) for cu in qs],
#             ignore_conflicts=True
#         )

#         return Response(
#             {"room_id": room.id, "type": "group", "created": created, "members": qs.count()},
#             status=201
#         )








# ---- MESSAGES LIST ----
# class MessageListView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, room_id):
#         # owner/history viewer can read any room
#         if has_permission(request.user, "chat:view_all_history"):
#             qs = Message.objects.filter(room_id=room_id).select_related("sender").prefetch_related("attachments","reactions").order_by("-id")[:50]
#             return Response({"read_only": True, "results": MessageSerializer(qs, many=True, context={"request": request}).data})

#         if not ensure_room_access(request.user, room_id):
#             return Response(status=404)

#         qs = Message.objects.filter(room_id=room_id).select_related("sender").prefetch_related("attachments","reactions").order_by("-id")[:50]
#         return Response({"read_only": False, "results": MessageSerializer(qs, many=True, context={"request": request}).data})





class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        # owner/history viewer can read any room
        if has_permission(request.user, "chat:view_all_history"):
            qs = (
                Message.objects
                .filter(room_id=room_id)
                .select_related("sender")
                .prefetch_related("attachments", "reactions")
                .order_by("-id")[:50]
            )
            return Response({
                "read_only": True,
                "chat_blocked": False,
                "results": MessageSerializer(
                    qs, many=True, context={"request": request}
                ).data
            })

        if not ensure_room_access(request.user, room_id):
            return Response(status=404)

        room = ChatRoom.objects.get(id=room_id)

        chat_blocked = False
        blocked_by = None
        blocked_at = None
        can_unblock = False

        # 🔒 Block info only applies to private chats
        if room.room_type == "private":
            other_id = ChatParticipant.objects.filter(
                room=room
            ).exclude(user=request.user).values_list(
                "user_id", flat=True
            ).first()

            block = UserBlock.objects.filter(
                Q(blocker=request.user, blocked_id=other_id) |
                Q(blocker_id=other_id, blocked=request.user)
            ).first()

            if block:
                chat_blocked = True
                blocked_at = block.blocked_at
                blocked_by = (
                    "me" if block.blocker_id == request.user.id else "other"
                )
                can_unblock = block.blocker_id == request.user.id
            last_message_id = (
            Message.objects
            .filter(room_id=room_id)
            .order_by("-id")
            .values_list("id", flat=True)
            .first()
        )

        if last_message_id:
            mark_room_read_and_clear_mentions(
                room_id=room_id,
                user=request.user,
              last_message_id=last_message_id
            )

        qs = (
            Message.objects
            .filter(room_id=room_id)
            .select_related("sender")
            .prefetch_related("attachments", "reactions")
            .order_by("-id")[:50]
        )

        return Response({
            "read_only": False,
            "chat_blocked": chat_blocked,
            "blocked_by": blocked_by,
            "blocked_at": blocked_at,
            "can_unblock": can_unblock,
            "results": MessageSerializer(
                qs, many=True, context={"request": request}
            ).data
        })


# ---- SEND MESSAGE ----

class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            effective_user, is_impersonating = get_effective_user(request)
        except PermissionError as e:
            return Response({"detail": str(e)}, status=403)

        # permission check applies to REAL user
        if not has_permission(request.user, "chat:send"):
            return Response({"detail":"Forbidden"}, status=403)

        # room access must be checked for EFFECTIVE user
   
        if not ensure_room_access(effective_user, room_id):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ROOM_ACCESS_DENIED",
                        "message": "Chat not available"
                    }
                },
                status=403
            )

        room = ChatRoom.objects.get(id=room_id)

        # private block applies to EFFECTIVE user
        if room.room_type == "private":
            other_id = ChatParticipant.objects.filter(
                room=room
            ).exclude(user=effective_user).values_list(
                "user_id", flat=True
            ).first()

            block = UserBlock.objects.filter(
                Q(blocker=effective_user, blocked_id=other_id) |
                Q(blocker_id=other_id, blocked=effective_user)
            ).select_related().first()

            if block:
                blocked_by = "me" if block.blocker_id == effective_user.id else "other"

                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "CHAT_BLOCKED",
                            "message": "You cannot send messages to this user",
                            "blocked_by": blocked_by,
                            "blocked_at": block.blocked_at
                        }
                    },
                    status=403
                )

        content = (request.data.get("content") or "").strip()
        files = request.FILES.getlist("attachments")

        if not content and not files:
            return Response({"detail":"content or attachments required"}, status=400)

        mention_ids = request.data.get("mention_user_ids", []) or []

        msg = create_message_with_mentions(
            room=room,
            sender=effective_user,
            content=content,
            mention_user_ids=mention_ids
        )

        attachment_type = request.data.get("attachment_type", "file")
        for f in files:
            MessageAttachment.objects.create(
                message=msg,
                file=f,
                attachment_type=attachment_type
            )

        # AI group auto-reply (only if real human message)
        # if room.room_type == "group" and not is_impersonating and has_permission(request.user, "chat:ai_group_autoreply"):
        #     from .tasks import group_ai_reply_if_no_human_response
        #     group_ai_reply_if_no_human_response.apply_async(args=[msg.id], countdown=180)
        if room.room_type == "group" and has_permission(request.user, "chat:ai_group_autoreply"):
           from django.conf import settings
           from .tasks import group_ai_reply_if_no_human_response

           if getattr(settings, "CELERY_ENABLED", False):
                group_ai_reply_if_no_human_response.apply_async(
                    args=[msg.id],
                    countdown=180
                )
      # REAL-TIME BROADCAST (THIS WAS MISSING)
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"room_{room.id}",
            {
                "type": "message_event",
                "message": serialize_message_payload(msg),
            }
        )



        return Response({
                "message_id": msg.id,
                "impersonated": is_impersonating
            }, status=201)


# ---- MARK READ (reduces tag count) ----
class MarkRoomReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        if has_permission(request.user, "chat:view_all_history"):
            return Response({"detail":"Read-only access"}, status=403)

        if not ensure_room_access(request.user, room_id):
            return Response(status=404)

        last_message_id = request.data.get("last_message_id")
        if not last_message_id:
            return Response({"detail":"last_message_id required"}, status=400)

        mark_room_read_and_clear_mentions(room_id=room_id, user=request.user, last_message_id=int(last_message_id))
        return Response({"success": True})

# ---- TAG COUNT (dashboard badge) ----
class MentionCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import MessageMention
        cnt = MessageMention.objects.filter(
            mentioned_user=request.user,
            seen_at__isnull=True,
            message__room__user_states__user=request.user,
            message__room__user_states__is_deleted=False
        ).count()
        return Response({"tagged_unread": cnt})

# ---- REACT (like/dislike role+override, group/private/ai) ----
class ReactMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        if has_permission(request.user, "chat:view_all_history"):
            return Response({"detail":"Read-only access"}, status=403)

        reaction = request.data.get("reaction")
        if reaction not in ("like","dislike"):
            return Response({"detail":"Invalid reaction"}, status=400)

        perm = "chat:react_like" if reaction == "like" else "chat:react_dislike"
        if not has_permission(request.user, perm):
            return Response({"detail":"Forbidden"}, status=403)

        msg = Message.objects.select_related("room","sender").get(id=message_id)
        if not ensure_room_access(request.user, msg.room_id):
            return Response({"detail":"Chat not available"}, status=403)

        existing = MessageReaction.objects.filter(message=msg, user=request.user).first()
        if not existing:
            MessageReaction.objects.create(message=msg, user=request.user, reaction=reaction)
        else:
            if existing.reaction == reaction:
                existing.delete()
                return Response({"reaction": None})
            existing.reaction = reaction
            existing.save(update_fields=["reaction"])

        # AI learning: learn from AI message OR AI room
        if msg.is_ai or msg.room.room_type == "ai":
            AiFeedback.objects.create(
                message=msg,
                user=request.user,
                reaction=reaction,
                role=request.user.role,
                knowledge_level=getattr(request.user,"knowledge_level",0),
                room_type=msg.room.room_type,
                clinic_id=msg.room.clinic_id,
            )

        return Response({"reaction": reaction})

# ---- BLOCK USER ----
# class BlockUserView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         if has_permission(request.user, "chat:view_all_history"):
#             return Response({"detail":"Read-only access"}, status=403)

#         if not has_permission(request.user, "chat:block_user"):
#             return Response({"detail":"Forbidden"}, status=403)

#         blocked_id = request.data.get("blocked_user_id")
#         if not blocked_id:
#             return Response({"detail":"blocked_user_id required"}, status=400)

#         UserBlock.objects.get_or_create(blocker=request.user, blocked_id=int(blocked_id))
#         return Response({"success": True})
# #unblock   
# class UnblockUserView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         if has_permission(request.user, "chat:view_all_history"):
#             return Response({"detail": "Read-only access"}, status=403)

#         if not has_permission(request.user, "chat:block_user"):
#             return Response({"detail": "Forbidden"}, status=403)

#         blocked_id = request.data.get("blocked_user_id")
#         if not blocked_id:
#             return Response({"detail": "blocked_user_id required"}, status=400)

#         deleted_count, _ = UserBlock.objects.filter(
#             blocker=request.user,
#             blocked_id=int(blocked_id)
#         ).delete()

#         if deleted_count == 0:
#             return Response(
#                 {"detail": "User was not blocked"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         return Response({"success": True})



class BlockUnblockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if has_permission(request.user, "chat:view_all_history"):
            return Response({"detail": "Read-only access"}, status=403)

        if not has_permission(request.user, "chat:block_user"):
            return Response({"detail": "Forbidden"}, status=403)

        user_id = request.data.get("user_id")
        action = request.data.get("action")

        if not user_id or action not in ("block", "unblock"):
            return Response(
                {"detail": "user_id and valid action required"},
                status=400
            )

        if int(user_id) == request.user.id:
            return Response(
                {"detail": "You cannot block yourself"},
                status=400
            )

        target_id = int(user_id)

        # 🔒 Check reverse block
        reverse_block = UserBlock.objects.filter(
            blocker_id=target_id,
            blocked=request.user
        ).first()

        if action == "block":
            if reverse_block:
                return Response(
                    {
                        "detail": (
                            "You are blocked by this user since "
                            f"{reverse_block.blocked_at}"
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            UserBlock.objects.get_or_create(
                blocker=request.user,
                blocked_id=target_id,
                defaults={"blocked_at": timezone.now()},
            )

        else:  # unblock
            deleted, _ = UserBlock.objects.filter(
                blocker=request.user,
                blocked_id=target_id
            ).delete()

            if deleted == 0:
                return Response(
                    {"detail": "User is not blocked by you"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response({"success": True, "action": action})



# ---- SOFT DELETE CHAT (per-user) ----
class SoftDeleteChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        if has_permission(request.user, "chat:view_all_history"):
            return Response({"detail":"Read-only access"}, status=403)

        if not has_permission(request.user, "chat:delete_chat"):
            return Response({"detail":"Forbidden"}, status=403)

        if not ChatParticipant.objects.filter(room_id=room_id, user=request.user).exists():
            return Response(status=404)

        st, _ = RoomUserState.objects.get_or_create(room_id=room_id, user=request.user)
        st.is_deleted = True
        st.deleted_at = timezone.now()
        st.save(update_fields=["is_deleted","deleted_at"])
        return Response({"success": True})
