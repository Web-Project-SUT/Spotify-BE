import os

from rest_framework import serializers


class MaxFileSize:
    message = "File exceeds the maximum allowed size."
    code = "file_too_large"

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes

    def __call__(self, value):
        if value.size > self.max_bytes:
            raise serializers.ValidationError(self.message, code=self.code)


class AllowedExtension:
    message = "Unsupported file type."
    code = "unsupported_file_type"

    def __init__(self, extensions: list[str]):
        self.extensions = tuple(ext.lower() for ext in extensions)

    def __call__(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in self.extensions:
            raise serializers.ValidationError(self.message, code=self.code)


class AudioSignature:
    """Sniffs magic bytes so a renamed .txt can't pass as an .mp3.

    `UploadedFile.content_type` is client-supplied and trivially spoofed, so
    extension/content-type checks alone aren't enough for audio.
    """

    message = "Unsupported file type."
    code = "unsupported_file_type"

    def __call__(self, value):
        head = value.read(12)
        value.seek(0)
        if not self._looks_like_audio(head):
            raise serializers.ValidationError(self.message, code=self.code)

    def _looks_like_audio(self, head: bytes) -> bool:
        if head[:3] == b"ID3":
            return True
        if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
            return True
        if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
            return True
        if head[:4] == b"fLaC":
            return True
        return False
