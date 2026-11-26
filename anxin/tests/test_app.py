import os
import tempfile
import unittest

import db
from app import app


class AnxinAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp_dir.name, "anxin-test.db")
        db.init_db()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def login_as(self, role):
        response = self.client.post('/api/session', json={'username': role + '_demo', 'password': 'Anxin2026!', 'role': role})
        self.assertEqual(response.status_code, 200)
        return response

    def tearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_react_page_routes(self):
        routes = [
            "/", "/login", "/elder/home", "/elder/sos", "/family/overview",
            "/community/dashboard", "/community/elders", "/community/alerts",
            "/volunteer/tasks", "/demo/simulator",
            "/not-a-real-page",
        ]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'<div id="root"></div>', response.data)
                response.close()

    def test_read_apis(self):
        expectations = {
            "/api/elder/home": "elder",
            "/api/family/overview": "readings",
            "/api/elders": "needs",
            "/api/volunteer/tasks": "tasks",
            "/api/dashboard": "kpi",
            "/api/alerts": "alerts",
        }
        for route, key in expectations.items():
            with self.subTest(route=route):
                self.login_as({'/api/elder/home': 'elder', '/api/family/overview': 'family', '/api/volunteer/tasks': 'volunteer'}.get(route, 'community'))
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(key, response.get_json())

    def test_session_lifecycle(self):
        response = self.login_as('community')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["home"], "/community/alerts")
        self.assertEqual(self.client.get("/api/session").get_json()["role"], "community")
        self.assertIsNone(self.client.delete("/api/session").get_json()["role"])
        self.assertEqual(self.client.post("/api/session", json={"role": "invalid"}).status_code, 400)

    def test_elder_and_simulator_writes(self):
        self.login_as('elder')
        self.assertTrue(self.client.post("/api/checkin").get_json()["ok"])
        self.assertTrue(self.client.post("/api/sos").get_json()["ok"])
        self.login_as('community')
        response = self.client.post("/api/simulator/trigger", json={"scenario": "fall"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])

    def test_alert_workflow(self):
        self.login_as('community')
        alert_id = self.client.post('/api/simulator/trigger', json={'scenario': 'fall'}).get_json()['alert_id']
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/dispatch", json={"assignee": "赵敏"}).get_json()["ok"])
        self.login_as('volunteer')
        task_ids = [task["id"] for task in self.client.get("/api/volunteer/tasks").get_json()["tasks"]]
        self.assertIn(alert_id, task_ids)
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/process", json={}).get_json()["ok"])
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/close", json={"result": "测试归档"}).get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
