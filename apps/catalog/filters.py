from django.utils import timezone
from django_filters import rest_framework as filters

from .models import Album, Track


class AlbumFilterSet(filters.FilterSet):
    artist = filters.UUIDFilter(field_name="artist_id")

    class Meta:
        model = Album
        fields = ["artist"]


class TrackFilterSet(filters.FilterSet):
    genre = filters.CharFilter(lookup_expr="iexact")
    artist = filters.UUIDFilter(field_name="artist_id")
    album = filters.UUIDFilter(field_name="album_id")
    earlyAccess = filters.BooleanFilter(method="filter_early_access")

    class Meta:
        model = Track
        fields = ["genre", "artist", "album"]

    def filter_early_access(self, queryset, name, value):
        if value:
            return queryset.filter(early_access_until__gt=timezone.now())
        return queryset
