import unittest
from fastapi.testclient import TestClient
from api.main import app

class TestSecretRoutesAbsent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_secret_store_route_returns_404(self):
        resp = self.client.post("/api/integrations/secrets", json={"profile_id": "test", "secrets": {"key": "value"}})
        self.assertEqual(resp.status_code, 404)

    def test_secret_get_route_returns_404(self):
        resp = self.client.get("/api/integrations/secrets/test")
        self.assertEqual(resp.status_code, 404)
