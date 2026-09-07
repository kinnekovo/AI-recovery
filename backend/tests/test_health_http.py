import unittest

from fastapi.testclient import TestClient

from app.database.session import get_db
from app.main import create_app


class FakeDb:
    def execute(self, statement):
        return None


class HealthHttpTest(unittest.TestCase):
    def test_health_endpoint_returns_provider_status_objects(self) -> None:
        app = create_app()

        def override_db():
            yield FakeDb()

        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)

        response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["database"]["status"], "ok")
        self.assertIn("ready", payload["providers"]["asr"])
        self.assertIn("missing_env", payload["providers"]["tts"])


if __name__ == "__main__":
    unittest.main()
