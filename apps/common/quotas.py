from abc import ABC, abstractmethod

from rest_framework.exceptions import PermissionDenied


class QuotaExceeded(PermissionDenied):
    default_code = "quota_exceeded"


class Quota(ABC):
    """Strategy base for tier-based limits. `limits[tier] is None` = unlimited."""

    limits: dict[str, int | None] = {}
    default_code = "quota_exceeded"

    def limit_for(self, tier: str) -> int | None:
        return self.limits.get(tier, self.limits.get("basic"))

    @abstractmethod
    def current_count(self, user) -> int: ...

    def check(self, user) -> None:
        limit = self.limit_for(user.tier)
        if limit is None:
            return
        if self.current_count(user) >= limit:
            raise QuotaExceeded(
                detail=f"Limit of {limit} reached for your subscription tier.",
                code=self.default_code,
            )


class PlaylistQuota(Quota):
    limits = {"basic": 6, "silver": 100, "gold": None}
    default_code = "playlist_quota_exceeded"

    def current_count(self, user) -> int:
        return user.playlists.count()


class DailyStreamQuota(Quota):
    limits = {"basic": 60, "silver": None, "gold": None}
    default_code = "daily_stream_quota_exceeded"

    def current_count(self, user) -> int:
        from django.utils import timezone

        today = timezone.now().date()
        return user.play_events.filter(played_at__date=today).count()


class AvatarUploadQuota(Quota):
    limits = {"basic": 0, "silver": None, "gold": None}
    default_code = "avatar_upload_quota_exceeded"

    def current_count(self, user) -> int:
        return 0
