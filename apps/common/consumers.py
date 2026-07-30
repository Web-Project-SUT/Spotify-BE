import json
from channels.generic.websocket import AsyncWebsocketConsumer

class GroupSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_{self.session_id}'

        # اتصال کاربر به گروه همگام‌سازی
        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # خروج کاربر از گروه
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action') # می‌تواند play, pause یا seek باشد
        progress = data.get('progress', 0)

        # ارسال رویداد به تمام کاربران حاضر در اتاق
        await self.channel_layer.group_send(
            self.session_group_name,
            {
                'type': 'session_event',
                'action': action,
                'progress': progress
            }
        )

    async def session_event(self, event):
        # دریافت رویداد از گروه و ارسال آن به فرانت‌اند
        await self.send(text_data=json.dumps({
            'action': event['action'],
            'progress': event['progress']
        }))