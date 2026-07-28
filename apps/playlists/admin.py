from django.contrib import admin

from .models import Playlist, PlaylistEntry


class PlaylistEntryInline(admin.TabularInline):
    model = PlaylistEntry
    extra = 0


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "is_public", "created_at"]
    search_fields = ["title", "owner__email"]
    inlines = [PlaylistEntryInline]
