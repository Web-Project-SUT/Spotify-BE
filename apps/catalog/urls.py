from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("albums", views.AlbumViewSet, basename="album")
router.register("tracks", views.TrackViewSet, basename="track")

urlpatterns = [
    path("streams/", views.StreamCreateView.as_view(), name="stream-create"),
    path("albums/<uuid:pk>/cover/", views.AlbumCoverView.as_view(), name="album-cover"),
    path("tracks/<uuid:pk>/cover/", views.TrackCoverView.as_view(), name="track-cover"),
    path("tracks/<uuid:pk>/audio/", views.TrackAudioView.as_view(), name="track-audio"),
    path("tracks/<uuid:pk>/download/", views.TrackDownloadView.as_view(), name="track-download"),
] + router.urls
