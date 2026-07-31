from django_filters import rest_framework as filters

from .models import ArtistPayout
from .services import parse_period


class ArtistPayoutFilterSet(filters.FilterSet):
    period = filters.CharFilter(method="filter_period", help_text="Payout month, `YYYY-MM`.")
    status = filters.ChoiceFilter(
        choices=ArtistPayout.Status.choices, help_text="`pending` or `paid`."
    )
    artist = filters.UUIDFilter(field_name="artist_id", help_text="Artist user id.")

    class Meta:
        model = ArtistPayout
        fields = ["period", "status", "artist"]

    def filter_period(self, queryset, name, value):
        return queryset.filter(period_month=parse_period(value))
