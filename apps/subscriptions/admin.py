from django.contrib import admin

from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["tier", "monthly_price", "is_active"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "starts_at", "expires_at"]
    list_filter = ["status", "plan"]
    search_fields = ["user__email"]
