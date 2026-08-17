from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AccountStatus, ArtistProfile, Notification, Role, User
from apps.accounts.tests.factories import UserFactory


def auth_headers(user):
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


class EnsureArtistProfileTests(APITestCase):
    def test_promoting_a_user_creates_the_profile(self):
        user = UserFactory(display_name="Promoted Person")
        self.assertFalse(ArtistProfile.objects.filter(user=user).exists())

        user.role = Role.ARTIST
        user.save()

        profile = ArtistProfile.objects.get(user=user)
        self.assertEqual(profile.stage_name, "Promoted Person")

    def test_stage_name_falls_back_to_the_username(self):
        user = UserFactory(display_name="", username="no_display_name")
        user.role = Role.ARTIST
        user.save()
        self.assertEqual(ArtistProfile.objects.get(user=user).stage_name, "no_display_name")

    def test_an_existing_profile_is_left_alone(self):
        user = UserFactory(role=Role.ARTIST, display_name="Renamed Since")
        ArtistProfile.objects.filter(user=user).update(stage_name="Original Stage Name")

        user.bio = "touched"
        user.save()

        self.assertEqual(ArtistProfile.objects.get(user=user).stage_name, "Original Stage Name")

    def test_listeners_get_no_profile(self):
        user = UserFactory()
        self.assertFalse(ArtistProfile.objects.filter(user=user).exists())

    def test_promotion_does_not_notify_reviewers(self):
        """A promoted artist is already active — they are not in the review queue,
        so support must not be told there is an application to review."""
        UserFactory(role=Role.SUPPORT)
        user = UserFactory()
        user.role = Role.ARTIST
        user.save()

        self.assertFalse(Notification.objects.filter(title="New artist application").exists())

    def test_registration_still_notifies_reviewers(self):
        support = UserFactory(role=Role.SUPPORT)
        response = self.client.post(
            "/api/auth/register/artist/",
            {"email": "applicant@demo.com", "password": "password123", "stageName": "Applicant"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        applicant = User.objects.get(email="applicant@demo.com")
        self.assertEqual(applicant.status, AccountStatus.PENDING)
        self.assertEqual(applicant.artist_profile.stage_name, "Applicant")
        self.assertEqual(
            Notification.objects.filter(recipient=support, title="New artist application").count(),
            1,
        )


class PromotedArtistEndpointsTests(APITestCase):
    """Before the signal existed these three all raised `RelatedObjectDoesNotExist`
    and returned 500 for anyone an admin had promoted."""

    def setUp(self):
        self.user = UserFactory(display_name="Promoted Person")
        self.user.role = Role.ARTIST
        self.user.save()

    def test_artist_me_patch(self):
        response = self.client.patch(
            "/api/artists/me/",
            {"stageName": "Renamed"},
            format="json",
            **auth_headers(self.user),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sample_works_list(self):
        response = self.client.get("/api/artists/me/sample-works/", **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_public_artist_page(self):
        response = self.client.get(f"/api/artists/{self.user.pk}/", **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_appears_in_the_artist_listing(self):
        response = self.client.get("/api/artists/", **auth_headers(self.user))
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(self.user.pk), ids)

    def test_missing_profile_reads_as_404_not_500(self):
        ArtistProfile.objects.filter(user=self.user).delete()
        response = self.client.get("/api/artists/me/sample-works/", **auth_headers(self.user))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ArtistListOrderingTests(APITestCase):
    def test_listing_is_ordered_so_pagination_is_stable(self):
        for name in ("Zed", "Ada", "Mia"):
            user = UserFactory(display_name=name)
            user.role = Role.ARTIST
            user.save()

        response = self.client.get("/api/artists/", **auth_headers(UserFactory()))
        names = [row["stageName"] for row in response.json()["results"]]
        self.assertEqual(names, sorted(names))
