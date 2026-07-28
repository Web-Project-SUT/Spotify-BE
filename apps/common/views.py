import mimetypes
import os

from django.conf import settings
from django.core.files.base import File
from django.http import Http404
from django.utils._os import safe_join
from rest_framework import generics, status
from rest_framework.response import Response

from . import media as media_utils
from .http import range_file_response


class MediaResourceView(generics.GenericAPIView):
    """A singleton binary sub-resource. PUT replaces it, DELETE clears it."""

    http_method_names = ["put", "delete"]
    media_fields: tuple[str, ...] = ()
    upload_serializer_class = None
    read_serializer_class = None
    quota_class = None

    def get_upload_serializer(self, *args, **kwargs):
        kwargs.setdefault("context", self.get_serializer_context())
        return self.upload_serializer_class(*args, **kwargs)

    def get_read_serializer(self, instance):
        return self.read_serializer_class(instance, context=self.get_serializer_context())

    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        if self.quota_class:
            self.quota_class().check(request.user)
        serializer = self.get_upload_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = {field: serializer.validated_data[field] for field in self.media_fields}
        media_utils.replace_files(instance, files)
        return Response(self.get_read_serializer(instance).data)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        media_utils.clear_files(instance, self.media_fields)
        return Response(status=status.HTTP_204_NO_CONTENT)


def serve_media(request, path):
    """DEBUG-only media server that supports Range, matching prod (nginx)."""
    try:
        full_path = safe_join(str(settings.MEDIA_ROOT), path)
    except ValueError as exc:
        raise Http404 from exc
    if not os.path.isfile(full_path):
        raise Http404
    content_type, _ = mimetypes.guess_type(full_path)
    file_handle = File(open(full_path, "rb"), name=os.path.basename(full_path))
    return range_file_response(
        file_handle, content_type or "application/octet-stream", request=request
    )
