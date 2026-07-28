from apps.common.permissions import IsOwnerOrReadOnly


class IsPlaylistOwner(IsOwnerOrReadOnly):
    owner_field = "owner"

    def has_object_permission(self, request, view, obj):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return obj.is_public or obj.owner_id == request.user.id
        return obj.owner_id == request.user.id
