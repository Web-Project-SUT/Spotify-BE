from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("playlists", views.PlaylistViewSet, basename="playlist")

urlpatterns = [
    path(
        "playlists/<uuid:playlist_id>/tracks/",
        views.PlaylistTracksView.as_view(),
        name="playlist-tracks",
    ),
    path(
        "playlists/<uuid:playlist_id>/tracks/<uuid:track_id>/",
        views.PlaylistTrackDetailView.as_view(),
        name="playlist-track-detail",
    ),
    path(
        "playlists/<uuid:pk>/cover/",
        views.PlaylistCoverView.as_view(),
        name="playlist-cover",
    ),
] + router.urls
