import json
from collections import defaultdict
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

# session_id -> set of channel_names currently connected. In-memory and
# proportionate to the InMemoryChannelLayer already configured for dev —
# this state lives only as long as the process does, same as the channel
# layer itself. No new model/migration: a group-listening session is a
# transient thing, not a record worth persisting.
_ROOM_MEMBERS: dict[str, set[str]] = defaultdict(set)


@database_sync_to_async
def _user_from_token(token):
    from apps.accounts.models import User

    try:
        validated = AccessToken(token)
        return User.objects.get(pk=validated["user_id"])
    except (TokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Populates scope["user"] from a `?token=` query param.

    The app authenticates with JWT access tokens kept in localStorage, not
    session cookies, so Channels' cookie-based AuthMiddlewareStack alone
    would leave every WebSocket connection anonymous. The browser
    WebSocket API also can't set an Authorization header, so the token
    travels as a query param instead — the same tradeoff already accepted
    for tokens living in localStorage (see utils/api.ts on the frontend).
    """

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await _user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)


class GroupSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            # ASGI requires an explicit accept/close response to
            # "websocket.connect" — returning without either just hangs.
            await self.close()
            return

        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_group_name = f"session_{self.session_id}"

        await self.channel_layer.group_add(self.session_group_name, self.channel_name)
        await self.accept()
        _ROOM_MEMBERS[self.session_id].add(self.channel_name)

    async def disconnect(self, close_code):
        room = _ROOM_MEMBERS.get(getattr(self, "session_id", None))
        if room is None:
            return
        room.discard(self.channel_name)
        await self.channel_layer.group_discard(self.session_group_name, self.channel_name)
        if not room:
            del _ROOM_MEMBERS[self.session_id]
            await self.channel_layer.group_send(
                self.session_group_name,
                {
                    "type": "session_event",
                    "event": "dissolved",
                    "sender_channel": self.channel_name,
                },
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        payload = {
            "type": "session_event",
            "action": data.get("action"),  # play, pause or seek
            "progress": data.get("progress", 0),
            "sender_channel": self.channel_name,
        }
        if data.get("trackId"):
            payload["track_id"] = data["trackId"]

        await self.channel_layer.group_send(self.session_group_name, payload)

    async def session_event(self, event):
        # The sender already applied this change locally; relaying it back
        # would feed the echo into its own state.
        if event.get("sender_channel") == self.channel_name:
            return
        message = {"action": event.get("action"), "progress": event.get("progress", 0)}
        if event.get("track_id"):
            message["trackId"] = event["track_id"]
        if event.get("event"):
            message["event"] = event["event"]
        await self.send(text_data=json.dumps(message))
