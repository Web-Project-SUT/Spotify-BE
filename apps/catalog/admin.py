from django.contrib import admin

from .models import Album, PlayEvent, Track


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "released_at"]
    search_fields = ["title", "artist__display_name", "artist__username"]


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "album", "genre", "play_count", "released_at"]
    list_filter = ["genre", "release_type"]
    search_fields = ["title", "artist__display_name", "artist__username"]


@admin.register(PlayEvent)
class PlayEventAdmin(admin.ModelAdmin):
    list_display = ["user", "track", "playlist", "played_at"]
    date_hierarchy = "played_at"
