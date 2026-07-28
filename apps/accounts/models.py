from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class Role(models.TextChoices):
    LISTENER = "listener", "Listener"
    ARTIST = "artist", "Artist"
    SUPPORT = "support", "Support"
    ADMIN = "admin", "Admin"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PENDING = "pending", "Pending"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


def avatar_path(instance, filename):
    return f"avatars/{instance.id}/{filename}"


class UserQuerySet(models.QuerySet):
    def with_tier(self):
        from apps.subscriptions.models import Subscription

        now = timezone.now()
        return self.annotate(
            active_tier=models.Subquery(
                Subscription.objects.filter(
                    user=models.OuterRef("pk"),
                    status="active",
                    expires_at__gt=now,
                ).values("plan__tier")[:1]
            )
        )


class UserManager(BaseUserManager.from_queryset(UserQuerySet)):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", Role.ADMIN)
        extra_fields.setdefault("status", AccountStatus.ACTIVE)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    username = models.SlugField(max_length=48, unique=True)
    display_name = models.CharField(max_length=60, blank=True)
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.LISTENER, db_index=True
    )
    status = models.CharField(
        max_length=16,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
        db_index=True,
    )
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=8, choices=Gender.choices, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to=avatar_path, null=True, blank=True)
    accepted_policy_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def tier(self) -> str:
        now = timezone.now()
        active = self.subscriptions.filter(status="active", expires_at__gt=now).first()
        return active.plan.tier if active else "basic"


class ArtistProfile(TimeStampedModel):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, related_name="artist_profile"
    )
    stage_name = models.CharField(max_length=80, db_index=True)
    portfolio_url = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="artist_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.stage_name


class Follow(TimeStampedModel):
    follower = models.ForeignKey(User, models.CASCADE, related_name="following_edges")
    following = models.ForeignKey(User, models.CASCADE, related_name="follower_edges")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="uniq_follow"),
            models.CheckConstraint(check=~Q(follower=models.F("following")), name="no_self_follow"),
        ]

    def __str__(self):
        return f"{self.follower_id} -> {self.following_id}"


class UserPreferences(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, related_name="preferences"
    )
    language = models.CharField(
        max_length=5,
        choices=[("en", "EN"), ("fa", "FA"), ("es", "ES")],
        default="en",
    )
    notif_limit = models.BooleanField(default=False)
    volume = models.FloatField(default=0.8, validators=[MinValueValidator(0), MaxValueValidator(1)])

    def __str__(self):
        return f"preferences for {self.user_id}"


class Notification(UUIDModel, TimeStampedModel):
    class Type(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        RELEASE = "release", "Release"
        APPROVAL = "approval", "Approval"
        SUPPORT = "support", "Support"

    recipient = models.ForeignKey(User, models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=140)
    message = models.TextField()
    type = models.CharField(max_length=16, choices=Type.choices)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]
