from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus, ArtistProfile, Role, User
from apps.accounts.tests.factories import UserFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class UserListTests(APITestCase):
    def setUp(self):
        self.admin = UserFactory(role=Role.ADMIN)

    def test_admin_lists_users(self):
        UserFactory(email="listed@demo.com")
        response = self.client.get("/api/users/", **auth_headers(self.admin))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = {row["email"] for row in response.json()["results"]}
        self.assertIn("listed@demo.com", emails)

    def test_support_cannot_list_users(self):
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.get("/api/users/", **auth_headers(support))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listener_cannot_list_users(self):
        response = self.client.get("/api/users/", **auth_headers(UserFactory()))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_and_role_filter(self):
        UserFactory(email="needle@demo.com", role=Role.SUPPORT)
        UserFactory(email="haystack@demo.com")
        headers = auth_headers(self.admin)

        found = self.client.get("/api/users/?search=needle", **headers).json()
        self.assertEqual([row["email"] for row in found["results"]], ["needle@demo.com"])

        support = self.client.get("/api/users/?role=support", **headers).json()
        self.assertEqual([row["email"] for row in support["results"]], ["needle@demo.com"])


class UserCreateTests(APITestCase):
    def setUp(self):
        self.admin = UserFactory(role=Role.ADMIN)

    def test_admin_creates_a_listener(self):
        response = self.client.post(
            "/api/users/",
            {"email": "made@demo.com", "password": "password123", "displayName": "Made Person"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="made@demo.com")
        self.assertEqual(created.role, Role.LISTENER)
        self.assertEqual(created.status, AccountStatus.ACTIVE)
        self.assertTrue(created.check_password("password123"))
        self.assertTrue(created.username)

    def test_creating_an_artist_creates_the_profile(self):
        response = self.client.post(
            "/api/users/",
            {
                "email": "artist.made@demo.com",
                "password": "password123",
                "displayName": "Made Artist",
                "role": "artist",
            },
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(email="artist.made@demo.com")
        self.assertEqual(ArtistProfile.objects.get(user=created).stage_name, "Made Artist")

    def test_duplicate_email_is_rejected(self):
        UserFactory(email="taken@demo.com")
        response = self.client.post(
            "/api/users/",
            {"email": "taken@demo.com", "password": "password123"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json()["fields"])

    def test_short_password_is_rejected(self):
        response = self.client.post(
            "/api/users/",
            {"email": "short@demo.com", "password": "abc"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.json()["fields"])

    def test_listener_cannot_create_users(self):
        response = self.client.post(
            "/api/users/",
            {"email": "nope@demo.com", "password": "password123"},
            format="json",
            **auth_headers(UserFactory()),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="nope@demo.com").exists())


class UserRoleUpdateTests(APITestCase):
    def setUp(self):
        self.admin = UserFactory(role=Role.ADMIN)
        self.target = UserFactory(display_name="Target Person")

    def test_admin_promotes_to_artist(self):
        response = self.client.patch(
            f"/api/users/{self.target.pk}/",
            {"role": "artist"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["role"], "artist")

        self.target.refresh_from_db()
        self.assertEqual(self.target.role, Role.ARTIST)
        self.assertEqual(ArtistProfile.objects.get(user=self.target).stage_name, "Target Person")

    def test_admin_suspends_an_account(self):
        response = self.client.patch(
            f"/api/users/{self.target.pk}/",
            {"status": "suspended"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target.refresh_from_db()
        self.assertEqual(self.target.status, AccountStatus.SUSPENDED)

    def test_admin_cannot_change_their_own_role(self):
        response = self.client.patch(
            f"/api/users/{self.admin.pk}/",
            {"role": "listener"},
            format="json",
            **auth_headers(self.admin),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, Role.ADMIN)

    def test_non_admin_cannot_change_a_role(self):
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.patch(
            f"/api/users/{self.target.pk}/",
            {"role": "admin"},
            format="json",
            **auth_headers(support),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_put_is_not_allowed(self):
        response = self.client.put(
            f"/api/users/{self.target.pk}/", {}, format="json", **auth_headers(self.admin)
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_public_detail_still_readable_by_anyone_signed_in(self):
        response = self.client.get(f"/api/users/{self.target.pk}/", **auth_headers(UserFactory()))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("email", response.json())
