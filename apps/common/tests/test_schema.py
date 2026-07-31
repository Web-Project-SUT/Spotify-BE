import io
import pathlib

import yaml
from django.conf import settings
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APITestCase

# The generator holds per-instance registry/endpoint state, so every test
# builds its own instance rather than sharing one across assertions.


class SchemaViewsTests(APITestCase):
    def test_schema_endpoint_returns_valid_yaml(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        parsed = yaml.safe_load(response.content)
        self.assertIn("paths", parsed)

    def test_swagger_ui_and_redoc_render(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        self.assertEqual(self.client.get("/api/redoc/").status_code, 200)


class SchemaGenerationTests(APITestCase):
    def test_generation_does_not_warn_or_error(self):
        # This is the test that would have caught the recommendation engine
        # and the entire payment flow being silently dropped from the schema.
        call_command("spectacular", "--fail-on-warn", stdout=io.StringIO())


class SchemaCoverageTests(APITestCase):
    """Every `/api/` route the URLconf knows about must appear in the schema."""

    EXCLUDED_PREFIXES = ("/api/schema/", "/api/docs/", "/api/redoc/")

    def _api_paths_from_urlconf(self, generator):
        generator._initialise_endpoints()
        paths = set()
        for path, _path_regex, method, callback in generator.endpoints:
            if not path.startswith("/api/") or path.startswith(self.EXCLUDED_PREFIXES):
                continue
            view = generator.create_view(callback, method)
            paths.add(generator.coerce_path(path, method, view))
        return paths

    def test_every_api_route_is_documented(self):
        generator = SchemaGenerator()
        schema = generator.get_schema(request=None, public=True)
        documented = set(schema["paths"].keys())
        expected = self._api_paths_from_urlconf(SchemaGenerator())
        missing = expected - documented
        self.assertFalse(missing, f"Routes missing from the OpenAPI schema: {sorted(missing)}")


class SchemaSecurityTests(APITestCase):
    PUBLIC_OPERATIONS = [
        ("/api/auth/register/listener/", "post"),
        ("/api/auth/register/artist/", "post"),
        ("/api/auth/login/", "post"),
        ("/api/auth/refresh/", "post"),
        ("/api/auth/password-reset/", "post"),
        ("/api/auth/password-reset/confirm/", "post"),
    ]

    def test_public_endpoints_have_no_security_requirement(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        for path, method in self.PUBLIC_OPERATIONS:
            operation = schema["paths"][path][method]
            self.assertFalse(
                operation.get("security"), f"{method.upper()} {path} should not require auth"
            )

    def test_protected_endpoint_requires_jwt(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        operation = schema["paths"]["/api/auth/me/"]["get"]
        self.assertTrue(operation.get("security"))


class SchemaDriftTests(APITestCase):
    def test_committed_schema_matches_generated(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        committed_path = pathlib.Path(settings.BASE_DIR) / "docs" / "openapi.yaml"
        self.assertTrue(committed_path.exists(), "docs/openapi.yaml is missing — regenerate it.")
        committed = yaml.safe_load(committed_path.read_text())
        self.assertEqual(
            committed,
            schema,
            "docs/openapi.yaml is stale — regenerate with `manage.py spectacular "
            "--file docs/openapi.yaml`.",
        )
