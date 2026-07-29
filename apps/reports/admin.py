from django.contrib import admin

from .models import ArtistPayout, PayoutPolicy


@admin.register(PayoutPolicy)
class PayoutPolicyAdmin(admin.ModelAdmin):
    list_display = ["effective_from", "per_stream_rate", "per_listener_rate"]
    list_editable = ["per_stream_rate", "per_listener_rate"]


@admin.register(ArtistPayout)
class ArtistPayoutAdmin(admin.ModelAdmin):
    list_display = ["artist", "period_month", "streams", "unique_listeners", "amount", "status"]
    list_filter = ["status", "period_month"]
    search_fields = ["artist__display_name", "artist__username"]
