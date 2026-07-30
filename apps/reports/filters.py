from django_filters import rest_framework as filters

from .models import ArtistPayout
from .services import parse_period


class ArtistPayoutFilterSet(filters.FilterSet):
    period = filters.CharFilter(method="filter_period")
    status = filters.ChoiceFilter(choices=ArtistPayout.Status.choices)
    artist = filters.UUIDFilter(field_name="artist_id")

    class Meta:
        model = ArtistPayout
        fields = ["period", "status", "artist"]

    def filter_period(self, queryset, name, value):
        return queryset.filter(period_month=parse_period(value))
