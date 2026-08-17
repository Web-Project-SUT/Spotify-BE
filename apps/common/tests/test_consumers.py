import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.tests.factories import UserFactory
from apps.common import consumers
from config.asgi import application


@database_sync_to_async
def _token_for(user) -> str:
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestGroupSessionConsumer:
    async def test_anonymous_connection_is_rejected(self):
        communicator = WebsocketCommunicator(application, "ws/session/anon-room/")
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()

    async def test_authenticated_connection_is_accepted(self):
        user = await database_sync_to_async(UserFactory)()
        token = await _token_for(user)
        communicator = WebsocketCommunicator(application, f"ws/session/room1/?token={token}")
        connected, _ = await communicator.connect()
        assert connected is True
        await communicator.disconnect()

    async def test_an_invalid_token_is_rejected(self):
        communicator = WebsocketCommunicator(
            application, "ws/session/room-bad-token/?token=not-a-real-token"
        )
        connected, _ = await communicator.connect()
        assert connected is False
        await communicator.disconnect()

    async def test_sender_does_not_receive_their_own_event(self):
        user = await database_sync_to_async(UserFactory)()
        token = await _token_for(user)
        communicator = WebsocketCommunicator(application, f"ws/session/room2/?token={token}")
        await communicator.connect()

        await communicator.send_json_to({"action": "play", "progress": 10})
        assert await communicator.receive_nothing(timeout=0.2) is True

        await communicator.disconnect()

    async def test_second_member_receives_the_event_including_track_id(self):
        user1 = await database_sync_to_async(UserFactory)()
        user2 = await database_sync_to_async(UserFactory)()
        token1 = await _token_for(user1)
        token2 = await _token_for(user2)
        room = "room3"
        c1 = WebsocketCommunicator(application, f"ws/session/{room}/?token={token1}")
        c2 = WebsocketCommunicator(application, f"ws/session/{room}/?token={token2}")
        await c1.connect()
        await c2.connect()

        await c1.send_json_to({"action": "play", "progress": 12, "trackId": "t9"})

        response = await c2.receive_json_from()
        assert response["action"] == "play"
        assert response["progress"] == 12
        assert response["trackId"] == "t9"
        assert await c1.receive_nothing(timeout=0.2) is True

        await c1.disconnect()
        await c2.disconnect()

    async def test_last_member_leaving_dissolves_the_room(self):
        user = await database_sync_to_async(UserFactory)()
        token = await _token_for(user)
        room = "room4"
        communicator = WebsocketCommunicator(application, f"ws/session/{room}/?token={token}")
        await communicator.connect()
        assert room in consumers._ROOM_MEMBERS

        await communicator.disconnect()
        assert room not in consumers._ROOM_MEMBERS

    async def test_one_of_two_members_leaving_does_not_dissolve_the_room(self):
        user1 = await database_sync_to_async(UserFactory)()
        user2 = await database_sync_to_async(UserFactory)()
        token1 = await _token_for(user1)
        token2 = await _token_for(user2)
        room = "room5"
        c1 = WebsocketCommunicator(application, f"ws/session/{room}/?token={token1}")
        c2 = WebsocketCommunicator(application, f"ws/session/{room}/?token={token2}")
        await c1.connect()
        await c2.connect()

        await c1.disconnect()
        assert room in consumers._ROOM_MEMBERS

        await c2.disconnect()
        assert room not in consumers._ROOM_MEMBERS
