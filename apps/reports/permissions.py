from rest_framework.permissions import BasePermission


class CanViewArtistStats(BasePermission):
    message = "Only the artist, staff, or a gold listener may view these stats."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if str(request.user.id) == str(view.kwargs.get("pk")):
            return True
        if request.user.role in ("support", "admin"):
            return True
        return request.user.tier == "gold"
