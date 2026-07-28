from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.models import Notification, User, UserPreferences
from apps.accounts.tests.factories import UserFactory, UserPreferencesFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


PREFERENCES_URL = "/api/auth/me/preferences/"


class PreferencesLazyCreationTests(APITestCase):
    def test_get_creates_defaults_on_first_request(self):
        user = UserFactory()
        response = self.client.get(PREFERENCES_URL, **auth_headers(user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["volume"], 80)
        self.assertEqual(response.data["language"], "en")
        self.assertEqual(response.data["notif_limit"], False)
        self.assertEqual(response.data["repeat_mode"], "off")
        self.assertEqual(response.data["shuffle"], False)
        self.assertEqual(response.data["playback_quality"], "high")

    def test_get_twice_creates_only_one_row(self):
        user = UserFactory()
        self.client.get(PREFERENCES_URL, **auth_headers(user))
        self.client.get(PREFERENCES_URL, **auth_headers(user))
        self.assertEqual(UserPreferences.objects.filter(user=user).count(), 1)


class PreferencesPatchTests(APITestCase):
    def test_patch_single_field_leaves_others_untouched(self):
        user = UserFactory()
        UserPreferencesFactory(user=user, volume=80, language="en")
        response = self.client.patch(
            PREFERENCES_URL, {"volume": 42}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["volume"], 42)
        self.assertEqual(response.data["language"], "en")

    def test_patch_all_fields_via_camel_case_body(self):
        user = UserFactory()
        response = self.client.patch(
            PREFERENCES_URL,
            {
                "language": "fa",
                "notifLimit": True,
                "volume": 33,
                "repeatMode": "one",
                "shuffle": True,
                "playbackQuality": "low",
            },
            format="json",
            **auth_headers(user),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["language"], "fa")
        self.assertEqual(response.data["notif_limit"], True)
        self.assertEqual(response.data["volume"], 33)
        self.assertEqual(response.data["repeat_mode"], "one")
        self.assertEqual(response.data["shuffle"], True)
        self.assertEqual(response.data["playback_quality"], "low")

    def test_preferences_isolated_per_user(self):
        user_a = UserFactory()
        user_b = UserFactory()
        self.client.patch(PREFERENCES_URL, {"volume": 10}, format="json", **auth_headers(user_a))
        response_b = self.client.get(PREFERENCES_URL, **auth_headers(user_b))
        self.assertEqual(response_b.data["volume"], 80)

    def test_updated_at_changes_on_patch(self):
        user = UserFactory()
        first = self.client.get(PREFERENCES_URL, **auth_headers(user))
        before = first.data["updated_at"]
        second = self.client.patch(
            PREFERENCES_URL, {"volume": 15}, format="json", **auth_headers(user)
        )
        self.assertNotEqual(second.data["updated_at"], before)


class PreferencesValidationTests(APITestCase):
    def test_volume_above_100_returns_400(self):
        user = UserFactory()
        response = self.client.patch(
            PREFERENCES_URL, {"volume": 101}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("volume", response.data["fields"])

    def test_volume_below_0_returns_400(self):
        user = UserFactory()
        response = self.client.patch(
            PREFERENCES_URL, {"volume": -1}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("volume", response.data["fields"])

    def test_invalid_language_returns_400(self):
        user = UserFactory()
        response = self.client.patch(
            PREFERENCES_URL, {"language": "xx"}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("language", response.data["fields"])

    def test_invalid_repeat_mode_returns_400(self):
        user = UserFactory()
        response = self.client.patch(
            PREFERENCES_URL, {"repeatMode": "bogus"}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("repeat_mode", response.data["fields"])


class PreferencesMethodTests(APITestCase):
    def test_put_not_allowed(self):
        user = UserFactory()
        response = self.client.put(
            PREFERENCES_URL, {"volume": 50}, format="json", **auth_headers(user)
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        user = UserFactory()
        response = self.client.delete(PREFERENCES_URL, **auth_headers(user))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class PreferencesAuthTests(APITestCase):
    def test_get_requires_authentication(self):
        response = self.client.get(PREFERENCES_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_requires_authentication(self):
        response = self.client.patch(PREFERENCES_URL, {"volume": 50}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PreferencesCrossDeviceTests(APITestCase):
    def test_preferences_persist_across_devices(self):
        user = UserFactory(email="multidevice@example.com", password="correct-pass")
        self.client.patch(PREFERENCES_URL, {"volume": 55}, format="json", **auth_headers(user))

        other_client = APIClient()
        login = other_client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "correct-pass"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        access = login.data["access"]
        response = other_client.get(
            PREFERENCES_URL, HTTP_AUTHORIZATION=f"Bearer {access}"
        )
        self.assertEqual(response.data["volume"], 55)


class PreferencesEmbeddedInMeTests(APITestCase):
    def test_me_embeds_preferences_without_creating_row(self):
        user = UserFactory()
        response = self.client.get("/api/auth/me/", **auth_headers(user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferences"]["volume"], 80)
        self.assertIsNone(response.data["preferences"]["updated_at"])
        self.assertEqual(UserPreferences.objects.filter(user=user).count(), 0)

    def test_login_embeds_preferences_without_creating_row(self):
        user = UserFactory(email="lazyread@example.com", password="correct-pass")
        response = self.client.post(
            "/api/auth/login/",
            {"email": user.email, "password": "correct-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["preferences"]["volume"], 80)
        self.assertEqual(UserPreferences.objects.filter(user=user).count(), 0)

    def test_register_listener_creates_a_row(self):
        response = self.client.post(
            "/api/auth/register/listener/",
            {
                "email": "newlistener@example.com",
                "password": "supersecret1",
                "displayName": "New Listener",
                "acceptedPolicy": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="newlistener@example.com")
        self.assertTrue(UserPreferences.objects.filter(user=user).exists())

    def test_preferences_not_writable_through_me_patch(self):
        user = UserFactory()
        response = self.client.patch(
            "/api/auth/me/",
            {"preferences": {"volume": 1}},
            format="json",
            **auth_headers(user),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["preferences"]["volume"], 80)
        self.assertEqual(UserPreferences.objects.filter(user=user).count(), 0)


class NotifyTests(APITestCase):
    def test_release_delivered_by_default(self):
        recipient = UserFactory()
        services.notify(
            [recipient], type=Notification.Type.RELEASE, title="t", message="m"
        )
        self.assertTrue(Notification.objects.filter(recipient=recipient).exists())

    def test_release_suppressed_when_notif_limit_true(self):
        recipient = UserFactory()
        UserPreferencesFactory(user=recipient, notif_limit=True)
        services.notify(
            [recipient], type=Notification.Type.RELEASE, title="t", message="m"
        )
        self.assertFalse(Notification.objects.filter(recipient=recipient).exists())

    def test_essential_types_always_delivered_even_with_notif_limit(self):
        for essential_type in (
            Notification.Type.SUBSCRIPTION,
            Notification.Type.APPROVAL,
            Notification.Type.SUPPORT,
        ):
            with self.subTest(type=essential_type):
                recipient = UserFactory()
                UserPreferencesFactory(user=recipient, notif_limit=True)
                services.notify(
                    [recipient], type=essential_type, title="t", message="m"
                )
                self.assertTrue(Notification.objects.filter(recipient=recipient).exists())

    def test_release_fan_out_avoids_n_plus_1(self):
        recipients = [UserFactory() for _ in range(5)]
        for recipient in recipients[:2]:
            UserPreferencesFactory(user=recipient, notif_limit=True)
        with self.assertNumQueries(2):
            services.notify(recipients, type=Notification.Type.RELEASE, title="t", message="m")
        self.assertEqual(Notification.objects.count(), 3)

    def test_essential_type_fan_out_has_no_suppression_query(self):
        recipients = [UserFactory() for _ in range(3)]
        with self.assertNumQueries(1):
            services.notify(
                recipients, type=Notification.Type.APPROVAL, title="t", message="m"
            )
        self.assertEqual(Notification.objects.count(), 3)


class PreferencesCascadeTests(APITestCase):
    def test_deleting_user_cascades_preferences(self):
        user = UserFactory()
        self.client.get(PREFERENCES_URL, **auth_headers(user))
        self.assertTrue(UserPreferences.objects.filter(pk=user.pk).exists())
        self.client.delete("/api/auth/me/", **auth_headers(user))
        self.assertFalse(UserPreferences.objects.filter(pk=user.pk).exists())
