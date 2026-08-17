from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import ArtistProfile, Follow, Notification, SampleWork, User, UserPreferences


class StreamrUserCreationForm(AdminUserCreationForm):
    """Django's admin user forms hard-code ``field_classes = {"username": UsernameField}``.

    ``UsernameField`` is a plain ``CharField``, but our ``username`` is a
    ``SlugField`` whose ``formfield()`` passes ``allow_unicode`` — which
    ``CharField`` rejects with a ``TypeError``, 500ing the add/change views.
    Clearing the mapping lets ``SlugField`` build its own form field.
    """

    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "username")
        field_classes = {}


class StreamrUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        field_classes = {}


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = StreamrUserCreationForm
    form = StreamrUserChangeForm
    ordering = ["-created_at"]
    list_display = ["email", "username", "role", "status", "is_staff"]
    list_filter = ["role", "status", "is_staff"]
    search_fields = ["email", "username", "display_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "username",
                    "display_name",
                    "role",
                    "status",
                    "birth_date",
                    "gender",
                    "bio",
                    "avatar",
                    "accepted_policy_at",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )


@admin.register(ArtistProfile)
class ArtistProfileAdmin(admin.ModelAdmin):
    list_display = ["stage_name", "user", "verified_at"]
    search_fields = ["stage_name", "user__email"]


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ["follower", "following", "created_at"]


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "language",
        "notif_limit",
        "volume",
        "repeat_mode",
        "shuffle",
        "playback_quality",
    ]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["recipient", "type", "title", "is_read", "created_at"]
    list_filter = ["type", "is_read"]


@admin.register(SampleWork)
class SampleWorkAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "created_at"]
    search_fields = ["title", "artist__stage_name"]
