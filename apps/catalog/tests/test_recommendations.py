from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.catalog.models import Track
from apps.playlists.models import Playlist, PlaylistEntry

User = get_user_model()

class RecommendationTests(APITestCase):
    def setUp(self):
        # ساخت و احراز هویت کاربر
        self.user = User.objects.create_user(email="test@example.com", username="testuser", password="password")
        self.client.force_authenticate(user=self.user)
        
        # ساخت هنرمند و آهنگ‌ها
        self.artist = User.objects.create_user(email="artist@example.com", username="testartist", password="password")
        self.track1 = Track.objects.create(title="Track 1", artist=self.artist)
        self.track2 = Track.objects.create(title="Track 2", artist=self.artist)
        
        # ساخت پلی‌لیست
        self.playlist = Playlist.objects.create(title="My Favorites", owner=self.user)
        
        # اضافه کردن آهنگ به پلی‌لیست از طریق مدل واسط PlaylistEntry
        PlaylistEntry.objects.create(playlist=self.playlist, track=self.track1, position=1)

    def test_get_recommendations(self):
        url = reverse('track-recommendations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # تبدیل UUID به استرینگ برای مقایسه درست با خروجی JSON
        self.assertTrue(any(track['id'] == str(self.track2.id) for track in response.data))