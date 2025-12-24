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
    Message, MessageAttachment, MessageReaction, AiFeedback , UserChatHistoryPreference
)
from notifications.models import Notification

from django.db.models import Q
from .guards import ensure_room_access
from .serializers import MessageSerializer , CreateClinicGroupSerializer ,DirectMessageCreateSerializer , AddGroupMembersSerializer ,BlockGroupMemberSerializer , BlockUnblockUserSerializer , BlockGroupMemberSerializer , ReactionListSerializer
from .services_rooms import ensure_clinic_group_room, get_or_create_private_room, get_or_create_ai_room, create_custom_group
from .services_messages import create_message_with_mentions, mark_room_read_and_clear_mentions
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from chat.realtime import serialize_message_payload ,serialize_reaction_payload




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
        # 🔹 Rooms where user is a participant (NORMAL MODE)
        participant_rooms = ChatRoom.objects.filter(
        participants__user=request.user,
        user_states__user=request.user,
        user_states__is_blocked=False,
    ).distinct().prefetch_related(
        "participants__user"
    ).order_by("-id")[:200]


        if participant_rooms.exists():
            rooms = participant_rooms
            read_only = False
        else:
            # 🔹 Audit-only rooms (OWNER / special roles)
            if not has_permission(request.user, "chat:view_all_history"):
                return Response({"detail": "Forbidden"}, status=403)

            rooms = ChatRoom.objects.prefetch_related(
                "participants__user"
            ).order_by("-id")[:200]
            read_only = True

        # 🔹 Last messages
        last_map = (
            Message.objects
            .filter(room__in=rooms)
            .values("room_id")
            .annotate(
                last_id=Max("id"),
                last_message_at=Max("created_at"),
            )
        )

        last_by_room = {
            x["room_id"]: {
                "last_id": x["last_id"],
                "last_message_at": x["last_message_at"],
            }
            for x in last_map
        }
        last_sender_by_room = {
        m.room_id: m.sender_id
        for m in Message.objects.filter(
            id__in=[x["last_id"] for x in last_map]
        )
    }
        states = {
            s.room_id: s
            for s in RoomUserState.objects.filter(room__in=rooms, user=request.user)
        }

        out = []
        for r in rooms:
            last_info = last_by_room.get(r.id, {})
            last_id = last_info.get("last_id")
            last_message_at = last_info.get("last_message_at")
            last_sender_id = last_sender_by_room.get(r.id)
            state = states.get(r.id)
            last_read = state.last_read_message_id if state else None

            unread = bool(
    not read_only and
    last_id and
    last_sender_id != request.user.id and  # ✅ KEY FIX
    (last_read is None or last_id > last_read)
)
            out.append({
                  "last_message_at": last_message_at,
                "room_id": r.id,
                "type": r.room_type,
                "clinic_id": r.clinic_id,
                "name": r.name,
                "unread": unread,
                "member_count": r.participants.count(),
                "members": [
                    {
                        "id": p.user.id,
                        "name": f"{p.user.first_name} {p.user.last_name}".strip()
                               or p.user.email,
                        "role": p.user.role,
                    }
                    for p in r.participants.all()
                ],
            })

        return Response({
            "read_only": read_only,
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
                        "message": "You do not have permission to create group chats"
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
                            "code": "NOT_CLINIC_MEMBER",
                            "message": "User must belong to the selected clinic"
                        }
                    },
                    status=403
                )

        # 🔑 Unique key
        safe_name = "-".join(name.lower().split())
        if group_kind == "clinic_all":
            ukey = f"clinic_all:{clinic_id}"
        elif group_kind == "clinic_role":
            ukey = f"clinic_role:{clinic_id}:{role}"
        else:  # clinic_custom
            ukey = f"clinic_custom:{clinic_id}:{safe_name}"

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

        # 🔹 Resolve members (ONCE)
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

        # 🔹 Always include creator
        member_ids = set(qs.values_list("user_id", flat=True))
        member_ids.add(request.user.id)

        qs = ClinicUser.objects.filter(
            clinic_id=clinic_id,
            user_id__in=member_ids
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
                "success": True,
                "data": {
                    "room_id": room.id,
                    "type": "group",
                    "group_kind": group_kind,
                    "clinic_id": clinic_id,
                    "created": created,
                    "members": qs.count(),
                }
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
        is_participant = ChatParticipant.objects.filter(
            room_id=room_id,
            user=request.user
        ).exists()

        if has_permission(request.user, "chat:view_all_history") and not is_participant:
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
        
        if not RoomUserState.objects.filter(
            room_id=room_id,
            user=request.user,
            # is_deleted=False,
            is_blocked=False   #
        ).exists():
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "ROOM_BLOCKED",
                        "message": "You no longer have access to this group"
                    }
                },
                status=403
    )

        
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
        pref = UserChatHistoryPreference.objects.filter(
            user=request.user,
            room_id=room_id
        ).first()

        qs = Message.objects.filter(room_id=room_id)

        if pref:
            qs = qs.filter(created_at__gt=pref.hide_history_before)

        qs = (
            qs.select_related("sender")
              .prefetch_related("attachments", "reactions")
              .order_by("-id")[:50]
        )

        # 5️⃣ Mark read safely
        last_message_id = qs[0].id if qs else None
        if last_message_id:
            mark_room_read_and_clear_mentions(
                room_id=room_id,
                user=request.user,
                last_message_id=last_message_id
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
        # 🔹 Fetch messages FIRST
        # qs = (
        #     Message.objects
        #     .filter(room_id=room_id)
        #     .select_related("sender")
        #     .prefetch_related("attachments", "reactions")
        #     .order_by("-id")[:50]
        # )

        # # 🔹 Mark as read HERE (safe)
        # last_message_id = qs[0].id if qs else None
        # if last_message_id:
        #     mark_room_read_and_clear_mentions(
        #         room_id=room_id,
        #         user=request.user,
        #         last_message_id=last_message_id
        #     )

        # return Response({
        #     "read_only": False,
        #     "chat_blocked": chat_blocked,
        #     "blocked_by": blocked_by,
        #     "blocked_at": blocked_at,
        #     "can_unblock": can_unblock,
        #     "results": MessageSerializer(
        #         qs, many=True, context={"request": request}
        #     ).data
        # })



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
                # 🚫 GROUP BLOCK CHECK
        if room.room_type == "group":
            state = RoomUserState.objects.filter(
                room=room,
                user=effective_user,
                is_blocked=False
            ).first()

            if state and state.is_blocked:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "GROUP_BLOCKED",
                            "message": "You are blocked from sending messages in this group"
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
                "success":True,
                "message_id": msg.id,
                "message_body": msg.content,
                "impersonated": is_impersonating
            }, status=201)
#-----Direct Message send View ------
class SendDirectMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not has_permission(request.user, "chat:create_private"):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You cannot send direct messages"
                    }
                },
                status=403
            )

        serializer = DirectMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data["user_ids"]
        content = serializer.validated_data["content"]

        channel_layer = get_channel_layer()
        results = []

        for other_user_id in user_ids:
            if other_user_id == request.user.id:
                continue  # safety

            other_user = User.objects.get(id=other_user_id)

            # 🔒 Block check (per user)
            if request.user.is_blocked or other_user.is_blocked:
                continue

            # 🔑 Get or create private room
            room = get_or_create_private_room(
                request.user.id,
                other_user.id
            )

            # 🔹 Ensure RoomUserState
            RoomUserState.objects.get_or_create(room=room, user=request.user)
            RoomUserState.objects.get_or_create(room=room, user=other_user)

            # 🔹 Create message
            message = create_message_with_mentions(
                room=room,
                sender=request.user,
                content=content,
                mention_user_ids=[]
            )

            # 🔹 Broadcast
            async_to_sync(channel_layer.group_send)(
                f"room_{room.id}",
                {
                    "type": "message_event",
                    "message": serialize_message_payload(message),
                }
            )

            results.append(
                {
                    "room_id": room.id,
                    "user_id": other_user.id,
                    "message_id": message.id
                }
            )

        return Response(
            {
                "success": True,
                "results": results
            },
            status=201
        )


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
        reaction = request.data.get("reaction")
        if reaction not in ("like", "dislike"):
            return Response({"detail": "Invalid reaction"}, status=400)

        perm = "chat:react_like" if reaction == "like" else "chat:react_dislike"
        if not has_permission(request.user, perm):
            return Response({"detail": "Forbidden"}, status=403)

        try:
            msg = Message.objects.select_related("room").get(id=message_id)
        except Message.DoesNotExist:
            return Response(status=404)

        room = msg.room

        if not ensure_room_access(request.user, room.id):
            return Response({"detail": "Chat not available"}, status=403)

        state = RoomUserState.objects.filter(room=room, user=request.user).first()
        if not state or state.is_blocked or state.is_deleted:
            return Response({"detail": "Action not allowed"}, status=403)

        existing = MessageReaction.objects.filter(
            message=msg, user=request.user
        ).first()

        removed = False
        if not existing:
            MessageReaction.objects.create(
                message=msg, user=request.user, reaction=reaction
            )
        else:
            if existing.reaction == reaction:
                existing.delete()
                removed = True
            else:
                existing.reaction = reaction
                existing.save(update_fields=["reaction"])

        # 🔴 REAL-TIME BROADCAST
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"room_{room.id}",
            {
                "type": "reaction_event",
                "message_id": msg.id,
                "reactions": {
                    "like": msg.reactions.filter(reaction="like").count(),
                    "dislike": msg.reactions.filter(reaction="dislike").count(),
                },
                "user_id": request.user.id,
                "reaction": None if removed else reaction,
            }
        )

        return Response(
            {
                "success": True,
                "reaction": None if removed else reaction
            }
        )


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
    def error(self, code, message):
        return {
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }
    

    def post(self, request):
        if has_permission(request.user, "chat:view_all_history"):
            return Response(
                self.error("READ_ONLY", "Read-only access"),
                status=403
            )

        if not has_permission(request.user, "chat:block_user"):
            return Response(
                self.error("FORBIDDEN", "You do not have permission"),
                status=403
            )

        serializer = BlockUnblockUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_id = serializer.validated_data["user_id"]
        action = serializer.validated_data["action"]

        if target_id == request.user.id:
            return Response(
                self.error("INVALID_ACTION", "You cannot block yourself"),
                status=400
            )

        reverse_block = UserBlock.objects.filter(
            blocker_id=target_id,
            blocked=request.user
        ).first()

        if action == "block":
            if reverse_block:
                return Response(
                    self.error(
                        "BLOCKED_BY_OTHER",
                        f"You are blocked since {reverse_block.blocked_at}"
                    ),
                    status=403
                )

            UserBlock.objects.get_or_create(
                blocker=request.user,
                blocked_id=target_id,
                defaults={"blocked_at": timezone.now()},
            )

        else:
            deleted, _ = UserBlock.objects.filter(
                blocker=request.user,
                blocked_id=target_id
            ).delete()

            if deleted == 0:
                return Response(
                    self.error(
                        "NOT_BLOCKED",
                        "User is not blocked by you"
                    ),
                    status=400
                )

        return Response({
            "success": True,
            "action": action,
            "user_id": target_id
        })



# ---- SOFT DELETE CHAT  ----
class SoftDeleteChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        if not has_permission(request.user, "chat:delete_chat"):
            return Response({"detail": "Forbidden"}, status=403)

        if not ChatParticipant.objects.filter(
            room_id=room_id,
            user=request.user
        ).exists():
            return Response(status=404)

        #  hide everything BEFORE now
        UserChatHistoryPreference.objects.update_or_create(
            user=request.user,
            room_id=room_id,
            defaults={
                "hide_history_before": timezone.now()
            }
        )

        # reset state
        RoomUserState.objects.update_or_create(
            room_id=room_id,
            user=request.user,
            defaults={
                "is_deleted": True,
                "deleted_at": timezone.now(),
                "last_read_message_id": None
            }
        )

        return Response({"success": True})




# add members
class AddGroupMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        if not (
            request.user.role == "owner" or
            has_permission(request.user, "chat:manage_group")
        ):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to add members"
                    }
                },
                status=403
            )

        room = ChatRoom.objects.filter(id=room_id, room_type="group").first()
        if not room:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Group not found"
                    }
                },
                status=404
            )

        if not ChatParticipant.objects.filter(room=room, user=request.user).exists():
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_MEMBER",
                        "message": "You are not a member of this group"
                    }
                },
                status=403
            )

        serializer = AddGroupMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data["user_ids"]

        users = User.objects.filter(
            id__in=user_ids,
            is_active=True,
            is_deleted=False,
            is_blocked=False
        )
        if users.count() != len(user_ids):
            return Response(
            {
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "One or more selected users do not exist"
                }
            },
            status=400
        )

        # if room.clinic_id:
        #     users = users.filter(
        #         clinicuser__clinic_id=room.clinic_id
        #     )
        if room.clinic_id:
            clinic_count = ClinicUser.objects.filter(
            clinic_id=room.clinic_id,
            user_id__in=user_ids
            ).count()

            if clinic_count != len(user_ids):
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "USER_NOT_IN_CLINIC",
                            "message": "One or more selected users are not in this clinic"
                        }
                    },
                    status=400
                )
                

        existing_ids = set(
            ChatParticipant.objects.filter(
                room=room,
                user_id__in=user_ids
            ).values_list("user_id", flat=True)
        )
        if existing_ids :
            return Response(
            {
                "success": False,
                "error": {
                    "code": "USER_ALREADY_MEMBER",
                    "message": "One or more selected users are already members"
                }
            },
            status=400
        )
           
        to_add = [u for u in users if u.id not in existing_ids]

        if not to_add:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "USER_ALREADY_MEMBER",
                        "message": "Selected users are already members of this group"
                    }
                },
                status=400
            )

        ChatParticipant.objects.bulk_create(
            [ChatParticipant(room=room, user=u) for u in to_add],
            ignore_conflicts=True
        )

        RoomUserState.objects.bulk_create(
            [RoomUserState(room=room, user=u) for u in to_add],
            ignore_conflicts=True
        )

        return Response(
            {
                "success": True,
                "data": {
                    "added": len(to_add),
                    "skipped": list(existing_ids),
                    "room_id": room.id
                }
            },
            status=201
        )


#room members view
# class ChatRoomMembersView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request, room_id):
#         room = ChatRoom.objects.filter(id=room_id).first()
#         if not room:
#             return Response(
#                 {
#                     "success": False,
#                     "error": {
#                         "code": "NOT_FOUND",
#                         "message": "Chat room not found"
#                     }
#                 },
#                 status=404
#             )

#         is_participant = ChatParticipant.objects.filter(
#             room=room,
#             user=request.user
#         ).exists()

#         # Owner / audit users can view without being participant
#         if not is_participant and not has_permission(
#             request.user, "chat:view_all_history"
#         ):
#             return Response(
#                 {
#                     "success": False,
#                     "error": {
#                         "code": "FORBIDDEN",
#                         "message": "You do not have access to this chat"
#                     }
#                 },
#                 status=403
#             )

#         participants = (
#             ChatParticipant.objects
#             .filter(room=room)
#             .select_related("user")
#             .order_by("user__first_name", "user__last_name")
#         )

#         results = []
#         for p in participants:
#             user = p.user
#             results.append({
#                 "id": user.id,
#                 "name": (
#                     f"{user.first_name} {user.last_name}".strip()
#                     or user.email
#                 ),
#                 "email": user.email,
#                 "role": user.role,
#                 "is_owner": user.role == "owner"
#             })

#         return Response(
#             {
#                 "success": True,
#                 "room_id": room.id,
#                 "room_type": room.room_type,
#                 "clinic_id": room.clinic_id if room.room_type == "group" else None,
#                 "count": len(results),
#                 "results": results
#             },
#             status=200
#         )

class ChatRoomMembersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = ChatRoom.objects.filter(id=room_id).first()
        if not room:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Chat room not found"
                    }
                },
                status=404
            )

        # Access control
        is_participant = ChatParticipant.objects.filter(
            room=room,
            user=request.user
        ).exists()

        if not is_participant and not has_permission(
            request.user, "chat:view_all_history"
        ):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have access to this chat"
                    }
                },
                status=403
            )

        # 🔑 Fetch participants WITH state
        participants = (
            ChatParticipant.objects
            .filter(room=room)
            .select_related("user")
            .prefetch_related("user__roomuserstate_set")
        )

        # Build state map (FAST)
        states = {
            s.user_id: s
            for s in RoomUserState.objects.filter(room=room)
        }

        results = []
        for p in participants:
            user = p.user
            state = states.get(user.id)

            results.append({
                "id": user.id,
                "name": (
                    f"{user.first_name} {user.last_name}".strip()
                    or user.email
                ),
                "email": user.email,
                "role": user.role,
                "is_owner": user.role == "owner",
                "is_blocked": bool(state and state.is_blocked),
                "is_deleted": bool(state and state.is_deleted),  # optional
            })

        return Response(
            {
                "success": True,
                "room_id": room.id,
                "room_type": room.room_type,
                "clinic_id": room.clinic_id if room.room_type == "group" else None,
                "count": len(results),
                "results": results
            },
            status=200
        )


#block from group
# class BlockGroupMemberView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, room_id):
#         if not (
#             request.user.role == "owner" or
#             has_permission(request.user, "chat:manage_group")
#         ):
#             return Response({
#                 "success": False,
#                 "message": "Permission denied",
#                 "data": None,
#                 "error": {
#                     "code": "FORBIDDEN",
#                     "message": "You do not have permission to manage this group"
#                 }
#             }, status=403)

#         serializer = BlockGroupMemberSerializer(data=request.data)
#         if not serializer.is_valid():
#             return Response({
#                 "success": False,
#                 "message": "Invalid request",
#                 "data": None,
#                 "error": {
#                     "code": "VALIDATION_ERROR",
#                     "message": serializer.errors
#                 }
#             }, status=400)

#         user_id = serializer.validated_data["user_id"]

#         if user_id == request.user.id:
#             return Response({
#                 "success": False,
#                 "message": "Invalid action",
#                 "data": None,
#                 "error": {
#                     "code": "INVALID_ACTION",
#                     "message": "You cannot block yourself"
#                 }
#             }, status=400)

#         state = RoomUserState.objects.filter(
#             room_id=room_id,
#             user_id=user_id
#         ).first()

#         if not state:
#             return Response({
#                 "success": False,
#                 "message": "User not found",
#                 "data": None,
#                 "error": {
#                     "code": "NOT_MEMBER",
#                     "message": "User is not a member of this group"
#                 }
#             }, status=404)

#         if state.is_blocked:
#             return Response({
#                 "success": False,
#                 "message": "Already blocked",
#                 "data": None,
#                 "error": {
#                     "code": "ALREADY_BLOCKED",
#                     "message": "User is already blocked"
#                 }
#             }, status=400)

#         state.is_blocked = True
#         state.save(update_fields=["is_blocked"])

#         return Response({
#             "success": True,
#             "message": "User blocked successfully",
#             "data": {
#                 "room_id": room_id,
#                 "user_id": user_id,
#                 "is_blocked": True
#             },
#             "error": None
#         }, status=200)

class BlockUnblockGroupMemberView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        # 🔐 Permission
        if not (
            request.user.role == "owner" or
            has_permission(request.user, "chat:manage_group")
        ):
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to manage this group"
                    }
                },
                status=403
            )

        serializer = BlockGroupMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        action = serializer.validated_data["action"]

        if user_id == request.user.id:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_ACTION",
                        "message": "You cannot block or unblock yourself"
                    }
                },
                status=400
            )

        # 🔎 Must be a group
        room = ChatRoom.objects.filter(id=room_id, room_type="group").first()
        if not room:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Group not found"
                    }
                },
                status=404
            )

        # 🔎 Must be member
        state = RoomUserState.objects.filter(
            room=room,
            user_id=user_id
        ).first()

        if not state:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "NOT_MEMBER",
                        "message": "User is not a member of this group"
                    }
                },
                status=404
            )

        # 🚫 BLOCK
        if action == "block":
            if state.is_blocked:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "ALREADY_BLOCKED",
                            "message": "User is already blocked"
                        }
                    },
                    status=400
                )

            state.is_blocked = True
            state.save(update_fields=["is_blocked"])

        # ✅ UNBLOCK
        else:
            if not state.is_blocked:
                return Response(
                    {
                        "success": False,
                        "error": {
                            "code": "NOT_BLOCKED",
                            "message": "User is not blocked"
                        }
                    },
                    status=400
                )

            state.is_blocked = False
            state.save(update_fields=["is_blocked"])

        return Response(
            {
                "success": True,
                "data": {
                    "room_id": room.id,
                    "user_id": user_id,
                    "is_blocked": state.is_blocked
                }
            },
            status=200
        )


#delete chat history
class SoftDeleteChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        if not has_permission(request.user, "chat:delete_chat"):
            return Response({"detail": "Forbidden"}, status=403)

        if not ChatParticipant.objects.filter(
            room_id=room_id,
            user=request.user
        ).exists():
            return Response(status=404)

        # hide everything BEFORE now
        UserChatHistoryPreference.objects.update_or_create(
            user=request.user,
            room_id=room_id,
            defaults={
                "hide_history_before": timezone.now()
            }
        )

        # reset state
        RoomUserState.objects.update_or_create(
            room_id=room_id,
            user=request.user,
            defaults={
                "is_deleted": True,
                "deleted_at": timezone.now(),
                "last_read_message_id": None
            }
        )

        return Response({"success": True})



class ClinicReactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reaction_type = request.GET.get("reaction")  # like | dislike | None

        # 🔹 Clinics user belongs to
        clinic_ids = ClinicUser.objects.filter(
            user=request.user
        ).values_list("clinic_id", flat=True)

        # 🔹 Base queryset
        qs = MessageReaction.objects.filter(
            message__room__clinic_id__in=clinic_ids
        ).select_related(
            "message",
            "message__room",
            "user"
        ).order_by("-created_at")

        # 🔹 Optional filter
        if reaction_type in ("like", "dislike"):
            qs = qs.filter(reaction=reaction_type)

        serializer = ReactionListSerializer(qs[:200], many=True)

        return Response({
            "success": True,
            "count": qs.count(),
            "results": serializer.data
        })