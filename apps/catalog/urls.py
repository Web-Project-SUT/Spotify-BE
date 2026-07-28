from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("albums", views.AlbumViewSet, basename="album")
router.register("tracks", views.TrackViewSet, basename="track")

urlpatterns = [
    path("streams/", views.StreamCreateView.as_view(), name="stream-create"),
] + router.urls
