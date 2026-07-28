from apps.common.permissions import IsOwnerOrReadOnly


class IsArtistOwner(IsOwnerOrReadOnly):
    owner_field = "artist"
