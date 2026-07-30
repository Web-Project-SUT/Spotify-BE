import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase


class MediaTestCase(APITestCase):
    """Isolates uploads under a throwaway MEDIA_ROOT, cleaned up after each test."""

    def setUp(self):
        super().setUp()
        self._media_root = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=self._media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self._media_root, True)


def make_image_file(name="cover.png", size=(2, 2), color="red"):
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def make_audio_file(name="track.mp3", payload=None):
    payload = payload if payload is not None else b"ID3" + bytes(200)
    return SimpleUploadedFile(name, payload, content_type="audio/mpeg")


def make_bogus_audio_file(name="fake.mp3"):
    return SimpleUploadedFile(name, b"not actually audio", content_type="audio/mpeg")
