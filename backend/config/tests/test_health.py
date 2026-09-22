from django.test import SimpleTestCase, TestCase


class LivenessTests(SimpleTestCase):
    def test_liveness(self):
        self.assertEqual(self.client.get("/health/live").json(), {"status": "ok"})


class ReadinessTests(TestCase):
    def test_readiness_checks_database(self):
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
