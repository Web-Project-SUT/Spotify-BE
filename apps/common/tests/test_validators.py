from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.common.validators import AllowedExtension, AudioSignature, MaxFileSize

from .helpers import make_audio_file, make_bogus_audio_file, make_image_file


class MaxFileSizeTests(SimpleTestCase):
    def test_rejects_oversized_file(self):
        validator = MaxFileSize(max_bytes=10)
        with self.assertRaises(ValidationError) as ctx:
            validator(make_image_file())
        self.assertEqual(ctx.exception.get_codes(), ["file_too_large"])

    def test_accepts_file_within_limit(self):
        validator = MaxFileSize(max_bytes=10_000_000)
        validator(make_image_file())  # does not raise


class AllowedExtensionTests(SimpleTestCase):
    def test_rejects_disallowed_extension(self):
        validator = AllowedExtension([".png", ".jpg"])
        with self.assertRaises(ValidationError) as ctx:
            validator(make_image_file(name="cover.gif"))
        self.assertEqual(ctx.exception.get_codes(), ["unsupported_file_type"])

    def test_accepts_allowed_extension(self):
        validator = AllowedExtension([".png", ".jpg"])
        validator(make_image_file(name="cover.png"))  # does not raise


class AudioSignatureTests(SimpleTestCase):
    def test_rejects_renamed_text_file(self):
        validator = AudioSignature()
        with self.assertRaises(ValidationError) as ctx:
            validator(make_bogus_audio_file(name="fake.mp3"))
        self.assertEqual(ctx.exception.get_codes(), ["unsupported_file_type"])

    def test_accepts_id3_tagged_mp3(self):
        validator = AudioSignature()
        validator(make_audio_file())  # does not raise
