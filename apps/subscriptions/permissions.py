from rest_framework.permissions import BasePermission

class BaseSubscriptionPermission(BasePermission):
    """
    کلاس پایه برای استخراج پلن فعال کاربر
    """
    def get_active_plan(self, request):
        # بررسی لاگین بودن کاربر
        if not request.user or not request.user.is_authenticated:
            return None
        
        # جستجو در دیتابیس برای پیدا کردن جدیدترین اشتراک فعال کاربر
        active_subscription = request.user.subscriptions.filter(status="active").first()
        
        # بررسی اینکه آیا اشتراک پیدا شده از نظر تاریخ هم معتبر است یا خیر
        if active_subscription and active_subscription.is_valid():
            return active_subscription.plan
            
        return None

class CanDownloadSong(BaseSubscriptionPermission):
    """پرمیشن بررسی دسترسی دانلود آهنگ"""
    message = "Your current subscription plan does not allow downloading songs."
    
    def has_permission(self, request, view):
        plan = self.get_active_plan(request)
        return plan is not None and plan.can_download

class CanAddAvatar(BaseSubscriptionPermission):
    """پرمیشن بررسی دسترسی آپلود عکس نمایه"""
    message = "Your current subscription plan does not allow adding avatars."
    
    def has_permission(self, request, view):
        plan = self.get_active_plan(request)
        return plan is not None and plan.can_add_avatar

class HasEarlyAccess(BaseSubscriptionPermission):
    """پرمیشن بررسی دسترسی زودهنگام به آهنگ‌های جدید"""
    message = "Early access is restricted to Gold subscribers."
    
    def has_permission(self, request, view):
        plan = self.get_active_plan(request)
        return plan is not None and plan.has_early_access