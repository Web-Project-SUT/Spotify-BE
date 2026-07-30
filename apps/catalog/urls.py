from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views
from .views import RecommendationAPIView

router = DefaultRouter()
router.register("albums", views.AlbumViewSet, basename="album")
router.register("tracks", views.TrackViewSet, basename="track")

urlpatterns = [
    path("streams/", views.StreamCreateView.as_view(), name="stream-create"),
    path('recommendations/', RecommendationAPIView.as_view(), name='track-recommendations'),
] + router.urls
