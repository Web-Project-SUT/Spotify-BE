import os

from apps.accounts.tests.factories import UserFactory
from apps.common.media import clear_files, replace_files, upload_filename

from .helpers import MediaTestCase, make_image_file


class UploadFilenameTests(MediaTestCase):
    def test_normalizes_stem_and_lowercases_extension(self):
        name = upload_filename("My Cool Cover!!.PNG")
        self.assertTrue(name.startswith("my-cool-cover-"))
        self.assertTrue(name.endswith(".png"))
        self.assertNotIn(" ", name)
        self.assertNotIn("!", name)

    def test_falls_back_to_file_for_unsluggable_stem(self):
        name = upload_filename("###.mp3")
        self.assertTrue(name.startswith("file-"))

    def test_two_calls_produce_different_names(self):
        self.assertNotEqual(upload_filename("cover.png"), upload_filename("cover.png"))


class ReplaceFilesTests(MediaTestCase):
    def test_replace_deletes_the_outgoing_blob(self):
        user = UserFactory()
        replace_files(user, {"avatar": make_image_file("first.png")})
        user.refresh_from_db()
        old_path = user.avatar.path
        self.assertTrue(os.path.exists(old_path))

        replace_files(user, {"avatar": make_image_file("second.png")})
        user.refresh_from_db()

        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(user.avatar.path))


class ClearFilesTests(MediaTestCase):
    def test_clear_deletes_blob_and_nulls_field(self):
        user = UserFactory()
        replace_files(user, {"avatar": make_image_file()})
        user.refresh_from_db()
        old_path = user.avatar.path

        clear_files(user, ("avatar",))
        user.refresh_from_db()

        self.assertFalse(os.path.exists(old_path))
        self.assertFalse(user.avatar)
