import os
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from werkzeug.security import check_password_hash

import db
from app import app


class AnxinAppTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp_dir.name, "anxin-test.db")
        shutil.copy2(self.original_db_path, db.DB_PATH)
        db.init_db()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def set_role(self, role):
        response = self.client.post("/api/session", json={"role": role})
        self.assertEqual(response.status_code, 200)

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
            "/api/elder/home": ("elder", "elder"),
            "/api/family/overview": ("family", "readings"),
            "/api/elders": ("community", "needs"),
            "/api/volunteer/tasks": ("volunteer", "tasks"),
            "/api/dashboard": ("community", "kpi"),
            "/api/alerts": ("community", "alerts"),
        }
        for route, (role, key) in expectations.items():
            with self.subTest(route=route):
                self.set_role(role)
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(key, response.get_json())
        self.set_role("family")
        self.assertEqual(self.client.get("/api/elders").status_code, 403)

    def test_session_lifecycle(self):
        response = self.client.post("/api/session", json={"role": "community"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["home"], "/community/dashboard")
        self.assertEqual(self.client.get("/api/session").get_json()["role"], "community")
        self.assertEqual(self.client.get("/api/family/overview").status_code, 403)
        self.assertEqual(self.client.get("/api/family/overview?preview=1").status_code, 200)
        self.set_role("family")
        self.assertEqual(
            self.client.post("/api/simulator/trigger?preview=1", json={"scenario": "fall"}).status_code,
            403,
        )
        self.assertIsNone(self.client.delete("/api/session").get_json()["role"])
        self.assertEqual(self.client.post("/api/session", json={"role": "invalid"}).status_code, 400)

    def test_user_registration_and_role_boundaries(self):
        token = uuid.uuid4().hex[:10]
        username = f"family_{token}"
        email = f"{username}@example.com"
        phone = f"138{str(int(token, 16))[-8:].zfill(8)}"
        response = self.client.post("/api/auth/register", json={
            "username": username,
            "email": email,
            "phone": phone,
            "role": "family",
            "password": "family-pass-123",
            "password_confirm": "family-pass-123",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["home"], "/family/overview")
        user = db.query_one("SELECT * FROM users WHERE username=?", (username,))
        self.assertNotEqual(user["password_hash"], "family-pass-123")
        self.assertTrue(check_password_hash(user["password_hash"], "family-pass-123"))
        self.assertEqual(user["account_type"], "user")
        self.assertEqual(user["role"], "family")
        self.assertEqual(self.client.get("/api/family/overview?preview=1").status_code, 200)
        self.assertEqual(self.client.get("/api/elders?preview=1").status_code, 403)
        self.assertEqual(self.client.get("/api/dashboard?preview=1").status_code, 403)
        self.assertEqual(self.client.post("/api/session", json={"role": "community"}).status_code, 403)
        duplicate = self.client.post("/api/auth/register", json={
            "username": username,
            "email": "another@example.com",
            "role": "family",
            "password": "family-pass-123",
            "password_confirm": "family-pass-123",
        })
        self.assertEqual(duplicate.status_code, 409)
        self.client.delete("/api/session")
        wrong_role = self.client.post("/api/auth/login", json={
            "account_type": "user", "role": "elder", "identifier": username, "password": "family-pass-123",
        })
        self.assertEqual(wrong_role.status_code, 403)
        correct_role = self.client.post("/api/auth/login", json={
            "account_type": "user", "role": "family", "identifier": email, "password": "family-pass-123",
        })
        self.assertEqual(correct_role.status_code, 200)
        self.assertEqual(correct_role.get_json()["home"], "/family/overview")

    def test_regular_accounts_can_register_for_each_role(self):
        role_apis = {
            "elder": ("/api/elder/home", ["/api/family/overview", "/api/dashboard", "/api/volunteer/tasks"]),
            "family": ("/api/family/overview", ["/api/elder/home", "/api/dashboard", "/api/volunteer/tasks"]),
            "community": ("/api/dashboard", ["/api/elder/home", "/api/family/overview", "/api/volunteer/tasks"]),
            "volunteer": ("/api/volunteer/tasks", ["/api/elder/home", "/api/family/overview", "/api/dashboard"]),
        }
        for role, home in [
            ("elder", "/elder/home"),
            ("family", "/family/overview"),
            ("community", "/community/dashboard"),
            ("volunteer", "/volunteer/tasks"),
        ]:
            with self.subTest(role=role):
                self.client.delete("/api/session")
                username = f"{role}_{uuid.uuid4().hex[:10]}"
                response = self.client.post("/api/auth/register", json={
                    "username": username,
                    "email": f"{username}@example.com",
                    "role": role,
                    "password": "role-pass-123",
                    "password_confirm": "role-pass-123",
                })
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.get_json()["home"], home)
                self.assertEqual(db.query_one("SELECT role FROM users WHERE username=?", (username,))["role"], role)
                allowed_api, forbidden_apis = role_apis[role]
                self.assertEqual(self.client.get(allowed_api).status_code, 200)
                for route in forbidden_apis:
                    with self.subTest(role=role, route=route):
                        self.assertEqual(self.client.get(route).status_code, 403)

    def test_legacy_user_roles_migrate_to_supported_role_set(self):
        legacy_path = os.path.join(self.temp_dir.name, "legacy-users.db")
        original_path = db.DB_PATH
        db.DB_PATH = legacy_path
        try:
            conn = sqlite3.connect(legacy_path)
            conn.executescript("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    password_hash TEXT NOT NULL,
                    account_type TEXT NOT NULL CHECK (account_type IN ('admin','user')),
                    role TEXT NOT NULL CHECK (role IN ('community','family')),
                    created_at TEXT NOT NULL
                );
                INSERT INTO users (username, email, password_hash, account_type, role, created_at)
                VALUES ('legacy-user', 'legacy@example.com', 'hash', 'user', 'family', '2026-01-01');
            """)
            conn.close()
            db.init_db()
            user = db.query_one("SELECT * FROM users WHERE username='legacy-user'")
            self.assertEqual(user["role"], "family")
            self.assertEqual(user["password_hash"], "hash")
            schema = db.query_one("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")["sql"]
            self.assertIn("'volunteer'", schema)
        finally:
            db.DB_PATH = original_path

    def test_admin_account_login_and_preview_access(self):
        missing = self.client.post("/api/auth/login", json={
            "account_type": "user", "role": "family", "identifier": "not-registered", "password": "anything",
        })
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.get_json()["code"], "USER_NOT_FOUND")
        response = self.client.post("/api/auth/login", json={
            "account_type": "admin", "identifier": "admin", "password": "admin123456",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["home"], "/")
        self.assertEqual(self.client.get("/api/family/overview?preview=1").status_code, 200)
        for route in [
            "/api/elder/home", "/api/family/overview", "/api/dashboard",
            "/api/elders", "/api/alerts", "/api/volunteer/tasks",
        ]:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        self.assertEqual(self.client.post("/api/checkin").status_code, 200)
        self.assertEqual(self.client.post("/api/session", json={"role": "elder"}).status_code, 200)
        self.assertEqual(self.client.get("/api/session").get_json()["role"], "elder")
        self.assertEqual(self.client.get("/api/session").get_json()["home"], "/")

    def test_elder_and_simulator_writes(self):
        self.assertEqual(self.client.post("/api/checkin").status_code, 401)
        self.set_role("elder")
        self.assertTrue(self.client.post("/api/checkin").get_json()["ok"])
        self.assertTrue(self.client.post("/api/sos").get_json()["ok"])
        self.set_role("community")
        response = self.client.post("/api/simulator/trigger", json={"scenario": "fall"})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["ok"])
        self.assertEqual(result["level"], "red")
        self.assertGreaterEqual(result["anomaly_percentile"], 80)
        self.assertEqual(result["baseline_scope"], "personal")
        alert = db.query_one("SELECT * FROM alerts WHERE id=?", (result["alert_id"],))
        self.assertEqual(alert["trigger_type"], "fall")
        self.assertIsNotNone(alert["anomaly_percentile"])
        self.assertIsNotNone(alert["baseline_scope"])
        need = db.query_one("SELECT * FROM needs WHERE source_alert_id=?", (result["alert_id"],))
        self.assertIsNotNone(need)
        self.assertEqual(need["category"], "visit")
        self.assertTrue(db.query_one("SELECT id FROM need_service_links WHERE need_id=?", (need["id"],)))

    def test_behavior_scenario_uses_personal_baseline(self):
        self.set_role("community")
        response = self.client.post("/api/simulator/trigger", json={"scenario": "no_water"})
        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["baseline_scope"], "personal")
        self.assertGreaterEqual(result["anomaly_percentile"], 80)
        self.assertIn("个人", result["msg"])
        latest = db.query_one(
            "SELECT * FROM sensor_readings WHERE elder_id=1 ORDER BY observed_at DESC LIMIT 1"
        )
        self.assertEqual(latest["source"], "synthetic_iot")

    def test_three_lists_include_service_resource_ledger(self):
        self.set_role("community")
        data = self.client.get("/api/elders").get_json()
        self.assertEqual(len(data["elders"]), 24)
        self.assertTrue(data["needs"])
        self.assertTrue(data["services"])
        self.assertTrue(any(item["category"] == "visit" for item in data["services"]))

    def test_legacy_sqlite_schema_migrates_without_resetting_data(self):
        legacy_path = os.path.join(self.temp_dir.name, "legacy.db")
        original_path = db.DB_PATH
        db.DB_PATH = legacy_path
        try:
            conn = sqlite3.connect(legacy_path)
            conn.executescript("""
                CREATE TABLE elders (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, live_alone INTEGER);
                CREATE TABLE alerts (id INTEGER PRIMARY KEY, elder_id INTEGER, created_at TEXT, status TEXT);
                CREATE TABLE needs (id INTEGER PRIMARY KEY, elder_id INTEGER, category TEXT,
                                    descr TEXT, urgency TEXT, status TEXT, provider TEXT);
                INSERT INTO elders (id, name, age, live_alone) VALUES (1, '旧档老人', 82, 1);
                INSERT INTO alerts (id, elder_id, created_at, status) VALUES (7, 1, '2026-01-01 08:00', 'pending');
                INSERT INTO needs (id, elder_id, category, descr, urgency, status)
                    VALUES (3, 1, 'visit', '旧需求', 'normal', '待对接');
            """)
            conn.close()

            db.init_db()

            columns = {row["name"] for row in db.query("PRAGMA table_info(alerts)")}
            need_columns = {row["name"] for row in db.query("PRAGMA table_info(needs)")}
            self.assertIn("anomaly_percentile", columns)
            self.assertIn("baseline_scope", columns)
            self.assertIn("source_alert_id", need_columns)
            self.assertEqual(db.query_one("SELECT name FROM elders WHERE id=1")["name"], "旧档老人")
            self.assertEqual(db.query_one("SELECT status FROM alerts WHERE id=7")["status"], "pending")
            self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM sensor_readings")["n"], 30)
        finally:
            db.DB_PATH = original_path

    def test_alert_workflow(self):
        self.set_role("community")
        alert_id = self.client.get("/api/alerts").get_json()["alerts"][0]["id"]
        initial_log_count = db.query_one(
            "SELECT COUNT(*) AS n FROM work_order_logs WHERE alert_id=?", (alert_id,)
        )["n"]
        self.client.delete("/api/session")
        self.assertEqual(self.client.post(f"/api/alerts/{alert_id}/dispatch", json={}).status_code, 401)
        self.set_role("volunteer")
        self.assertEqual(self.client.post(f"/api/alerts/{alert_id}/process").status_code, 409)
        self.set_role("community")
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/dispatch", json={"assignee": "赵敏"}).get_json()["ok"])
        self.set_role("volunteer")
        task_ids = [task["id"] for task in self.client.get("/api/volunteer/tasks").get_json()["tasks"]]
        self.assertIn(alert_id, task_ids)
        self.assertTrue(self.client.post(f"/api/alerts/{alert_id}/process", json={}).get_json()["ok"])
        receipt = self.client.post(f"/api/alerts/{alert_id}/close", json={"result": "测试处置回执"})
        self.assertEqual(receipt.get_json()["status"], "follow_up")
        self.assertEqual(db.query_one("SELECT status FROM alerts WHERE id=?", (alert_id,))["status"], "follow_up")
        self.set_role("family")
        self.assertEqual(self.client.post(f"/api/alerts/{alert_id}/follow-up", json={"result": "老人确认服务完成", "satisfaction": 5}).status_code, 200)
        self.assertEqual(db.query_one("SELECT status FROM alerts WHERE id=?", (alert_id,))["status"], "closed")
        self.assertEqual(
            db.query_one("SELECT COUNT(*) AS n FROM work_order_logs WHERE alert_id=?", (alert_id,))["n"],
            initial_log_count + 4,
        )
        self.assertEqual(db.query_one("SELECT COUNT(*) AS n FROM follow_up_records WHERE alert_id=?", (alert_id,))["n"], 1)


if __name__ == "__main__":
    unittest.main()
