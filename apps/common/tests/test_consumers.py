import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application

@pytest.mark.asyncio
class TestGroupSessionConsumer:
    async def test_websocket_connection_and_sync(self):
        # شبیه‌سازی اتصال یک کاربر به جلسه شماره 123
        communicator = WebsocketCommunicator(application, "ws/session/123/")
        connected, subprotocol = await communicator.connect()
        
        # بررسی موفقیت‌آمیز بودن اتصال
        assert connected is True

        # شبیه‌سازی ارسال رویداد "پخش آهنگ" از طرف کاربر
        test_event = {
            "action": "play",
            "progress": 45
        }
        await communicator.send_json_to(test_event)

        # بررسی دریافت رویداد از گروه (چون پیام به همه اعضای اتاق برمی‌گردد)
        response = await communicator.receive_json_from()
        
        # بررسی صحت داده‌های دریافت شده
        assert response["action"] == "play"
        assert response["progress"] == 45

        # قطع اتصال
        await communicator.disconnect()