from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.common.validators import AllowedExtension, MaxFileSize
from apps.subscriptions.models import Subscription

from . import services
from .models import AccountStatus, ArtistProfile, Follow, SampleWork, User, UserPreferences


class FollowCountsMixin:
    """Social numbers for a profile payload, aggregated server-side.

    `Follow.follower` is related_name="following_edges" and `Follow.following`
    is related_name="follower_edges" — crossed on purpose, so a user's
    *followers* are their `follower_edges` and the accounts they follow are
    their `following_edges`.
    """

    def _follow_target(self, obj) -> User:
        """The User the counts are about — overridden where obj isn't one."""
        return obj

    def get_follower_count(self, obj) -> int:
        return self._follow_target(obj).follower_edges.count()

    def get_following_count(self, obj) -> int:
        return self._follow_target(obj).following_edges.count()

    def get_is_following(self, obj) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        target = self._follow_target(obj)
        if request.user.pk == target.pk:
            return False
        return Follow.objects.filter(follower=request.user, following=target).exists()


class ArtistListSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="user_id", read_only=True)
    verified = serializers.SerializerMethodField()

    class Meta:
        model = ArtistProfile
        fields = ["id", "stage_name", "verified"]

    def get_verified(self, obj) -> bool:
        return obj.user.status == AccountStatus.ACTIVE


class ArtistDetailSerializer(FollowCountsMixin, serializers.ModelSerializer):
    id = serializers.UUIDField(source="user_id", read_only=True)
    bio = serializers.CharField(source="user.bio", read_only=True)
    verified = serializers.SerializerMethodField()
    total_plays = serializers.SerializerMethodField()
    total_listeners = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = ArtistProfile
        fields = [
            "id",
            "stage_name",
            "portfolio_url",
            "bio",
            "verified",
            "total_plays",
            "total_listeners",
            "follower_count",
            "is_following",
        ]

    # The instance is an ArtistProfile; the follow edges hang off its User.
    def _follow_target(self, obj) -> User:
        return obj.user

    def get_verified(self, obj) -> bool:
        return obj.user.status == AccountStatus.ACTIVE

    def get_total_plays(self, obj) -> int:
        return obj.user.tracks.aggregate(total=Sum("play_count"))["total"] or 0

    def get_total_listeners(self, obj) -> int:
        return obj.user.tracks.aggregate(total=Sum("unique_listener_count"))["total"] or 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_gold = bool(request and request.user.is_authenticated and request.user.tier == "gold")
        if not is_gold:
            data.pop("total_plays", None)
            data.pop("total_listeners", None)
        return data


class PendingArtistSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="user_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ArtistProfile
        fields = ["id", "stage_name", "email", "portfolio_url", "created_at"]
        read_only_fields = fields


class ArtistRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, max_length=500)


class ArtistMeSerializer(serializers.ModelSerializer):
    bio = serializers.CharField(source="user.bio", required=False, allow_blank=True)

    class Meta:
        model = ArtistProfile
        fields = ["stage_name", "portfolio_url", "bio"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        instance = super().update(instance, validated_data)
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save(update_fields=list(user_data.keys()))
        return instance


class UserPublicSerializer(FollowCountsMixin, serializers.ModelSerializer):
    tier = serializers.CharField(read_only=True)
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "display_name",
            "role",
            "avatar",
            "bio",
            "tier",
            "follower_count",
            "following_count",
            "is_following",
        ]


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            "language",
            "notif_limit",
            "volume",
            "repeat_mode",
            "shuffle",
            "playback_quality",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class MySubscriptionSerializer(serializers.ModelSerializer):
    """The caller's own active subscription, read-only.

    `User.tier` already tells the frontend *what* it bought; the expiry and
    period are what let it show when the plan runs out and offer a renewal
    (doc.tex §3.2 requires both the interval and "users' need to renew it").
    Nested on /auth/me/ rather than given its own endpoint, since it is only
    ever wanted alongside the tier that is already there.
    """

    tier = serializers.CharField(source="plan.tier", read_only=True)

    class Meta:
        model = Subscription
        fields = ["tier", "period_months", "starts_at", "expires_at", "status"]
        read_only_fields = fields


class UserMeSerializer(serializers.ModelSerializer):
    tier = serializers.CharField(read_only=True)
    preferences = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "display_name",
            "role",
            "status",
            "tier",
            "bio",
            "avatar",
            "birth_date",
            "gender",
            "created_at",
            "preferences",
            "subscription",
        ]
        read_only_fields = ["id", "username", "role", "status", "tier", "created_at"]

    @extend_schema_field(UserPreferencesSerializer)
    def get_preferences(self, obj):
        # A read must not write: fall back to an unsaved instance (defaults,
        # updated_at=null) rather than calling services.get_preferences(),
        # since this serializer backs /me, register, and login responses
        # where a lazy INSERT would be a surprising side effect.
        prefs = getattr(obj, "preferences", None) or UserPreferences(user=obj)
        return UserPreferencesSerializer(prefs).data

    @extend_schema_field(MySubscriptionSerializer(allow_null=True))
    def get_subscription(self, obj):
        # Same window as User.tier, so the two can never disagree.
        active = (
            obj.subscriptions.filter(
                status=Subscription.Status.ACTIVE, expires_at__gt=timezone.now()
            )
            .select_related("plan")
            .first()
        )
        return MySubscriptionSerializer(active).data if active else None


class MeUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ["display_name", "email", "bio", "password"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance


class RegisterListenerSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    display_name = serializers.CharField(max_length=60, required=True)
    accepted_policy = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "display_name",
            "birth_date",
            "gender",
            "accepted_policy",
        ]

    def validate_accepted_policy(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the privacy policy.")
        return value

    def create(self, validated_data):
        return services.register_listener(
            email=validated_data["email"],
            password=validated_data["password"],
            display_name=validated_data["display_name"],
            birth_date=validated_data.get("birth_date"),
            gender=validated_data.get("gender", ""),
            accepted_policy=validated_data["accepted_policy"],
        )


class RegisterArtistSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    stage_name = serializers.CharField(max_length=80)
    portfolio = serializers.URLField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["email", "password", "stage_name", "portfolio"]

    def create(self, validated_data):
        return services.register_artist(
            email=validated_data["email"],
            password=validated_data["password"],
            stage_name=validated_data["stage_name"],
            portfolio_url=validated_data.get("portfolio", ""),
        )


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserMeSerializer(self.user, context=self.context).data
        return data


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


class AvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.ImageField(
        validators=[
            MaxFileSize(settings.MEDIA_IMAGE_MAX_BYTES),
            AllowedExtension(settings.MEDIA_IMAGE_EXTENSIONS),
        ]
    )


class SampleWorkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleWork
        fields = ["id", "title", "file", "created_at"]
        read_only_fields = fields


class SampleWorkUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField(
        validators=[
            MaxFileSize(settings.MEDIA_AUDIO_MAX_BYTES),
            AllowedExtension(settings.MEDIA_IMAGE_EXTENSIONS + settings.MEDIA_AUDIO_EXTENSIONS),
        ]
    )

    class Meta:
        model = SampleWork
        fields = ["title", "file"]

    def create(self, validated_data):
        artist = self.context["request"].user.artist_profile
        return SampleWork.objects.create(artist=artist, **validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import Notification

        model = Notification
        fields = ["id", "title", "message", "type", "is_read", "link", "created_at"]
        read_only_fields = fields
