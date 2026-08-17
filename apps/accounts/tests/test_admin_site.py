from django.test import TestCase

from apps.accounts.models import AccountStatus, ArtistProfile, Role, User
from apps.accounts.tests.factories import UserFactory


class UserAdminTests(TestCase):
    """The Django admin is the only user-management surface, so its User pages
    are load-bearing: they 500'd for a long time because `username` is a
    `SlugField` and Django's admin forms force a `UsernameField` onto it."""

    def setUp(self):
        self.admin = UserFactory(
            role=Role.ADMIN, status=AccountStatus.ACTIVE, is_staff=True, is_superuser=True
        )
        self.client.force_login(self.admin)

    def test_add_page_loads(self):
        response = self.client.get("/admin/accounts/user/add/")
        self.assertEqual(response.status_code, 200)

    def test_change_page_loads(self):
        response = self.client.get(f"/admin/accounts/user/{self.admin.pk}/change/")
        self.assertEqual(response.status_code, 200)

    def test_changelist_loads(self):
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)

    def test_admin_creates_a_user(self):
        response = self.client.post(
            "/admin/accounts/user/add/",
            {
                "email": "new.admin.made@demo.com",
                "username": "new_admin_made",
                "password1": "Str0ngPassw0rd!",
                "password2": "Str0ngPassw0rd!",
                "usable_password": "true",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.filter(email="new.admin.made@demo.com").first()
        self.assertIsNotNone(created)
        self.assertEqual(created.role, Role.LISTENER)

    def test_admin_promotes_a_user_to_artist(self):
        user = UserFactory(display_name="Promoted Person")
        response = self.client.post(
            f"/admin/accounts/user/{user.pk}/change/",
            {
                "email": user.email,
                "username": user.username,
                "display_name": user.display_name,
                "role": Role.ARTIST,
                "status": AccountStatus.ACTIVE,
                "birth_date": "",
                "gender": "",
                "bio": "",
                "accepted_policy_at_0": "",
                "accepted_policy_at_1": "",
                "is_active": "on",
                "_save": "Save",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.role, Role.ARTIST)
        self.assertTrue(ArtistProfile.objects.filter(user=user).exists())
