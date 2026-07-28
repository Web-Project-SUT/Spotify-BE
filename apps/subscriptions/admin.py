from django.contrib import admin
from .models import SubscriptionPlan, Subscription

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    # تعیین فیلدهای نمایش داده شده برای پلن‌ها (بدون is_active)
    list_display = ('tier', 'monthly_price', 'daily_stream_limit', 'playlist_limit')
    list_editable = ('monthly_price',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # تنظیم فیلدهای نمایش داده شده بر اساس ساختار جدید مدل Subscription
    list_display = ('user', 'plan', 'status', 'starts_at', 'expires_at')
    list_filter = ('status', 'plan')