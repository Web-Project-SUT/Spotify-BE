from django.contrib import admin

from .models import Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["subject", "author", "status", "created_at"]
    search_fields = ["subject", "author__email"]
    list_filter = ["status"]
    inlines = [TicketMessageInline]
