from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from chat.models import RoomUserState, Message
from chat.services_messages import mark_room_read_and_clear_mentions


@database_sync_to_async
def can_user_connect(user, room_id):
    return RoomUserState.objects.filter(
        room_id=room_id,
        user=user,
        is_blocked=False,   
    ).exists()


@database_sync_to_async
def mark_room_read_on_delivery(room_id, user):
    last_message_id = (
        Message.objects.filter(room_id=room_id)
        .order_by("-id")
        .values_list("id", flat=True)
        .first()
    )

    if last_message_id:
        mark_room_read_and_clear_mentions(
            room_id=room_id,
            user=user,
            last_message_id=last_message_id,
        )


class ChatRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.group_name = f"room_{self.room_id}"

        allowed = await can_user_connect(user, self.room_id)
        if not allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()
        self._marked_read = False

        await self.send_json(
            {
                "type": "connected",
                "room_id": self.room_id,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, data):
        if data.get("type") == "typing":
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "typing_event",
                    "user_id": self.scope["user"].id,
                },
            )

    async def message_event(self, event):
        await self.send_json(
            {
                "type": "message",
                "data": event["message"],
            }
        )

        if not self._marked_read:
            self._marked_read = True
            await mark_room_read_on_delivery(
                self.room_id,
                self.scope["user"],
            )

    async def typing_event(self, event):
        await self.send_json(
            {
                "type": "typing",
                "user_id": event["user_id"],
            }
        )
    async def reaction_event(self, event):
        await self.send_json({
            "type": "reaction",
            "message_id": event["message_id"],
            "reactions": event["reactions"],
            "user_id": event["user_id"],
            "reaction": event["reaction"],
        })
