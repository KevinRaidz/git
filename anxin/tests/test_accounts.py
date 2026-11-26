import os
import tempfile
import unittest
import db
from app import app


class AccountAccessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp.name, 'accounts.db')
        db.init_db()
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def login(self, account_role, **extra):
        data = dict(username=account_role + '_demo', password='Anxin2026!', role=account_role)
        data.update(extra)
        return self.client.post('/api/session', json=data)

    def test_unauthenticated_cannot_read_or_write(self):
        for url in ['/api/elder/home', '/api/family/overview', '/api/alerts', '/api/volunteer/tasks']:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post('/api/sos').status_code, 401)
        self.assertEqual(self.client.post('/api/session', json={'role': 'community'}).status_code, 400)

    def test_credentials_and_role_validated(self):
        self.assertEqual(self.login('elder', password='wrong').status_code, 401)
        self.assertEqual(self.login('elder', role='community').status_code, 403)
        session = self.client.get('/api/session').get_json()
        self.assertIsNone(session['user'])
        self.assertTrue(session['demo_login_enabled'])
        user = self.login('elder').get_json()['user']
        self.assertEqual(user['role'], 'elder')
        self.assertNotIn('password_hash', user)

    def test_session_can_disable_public_demo_credentials(self):
        previous = app.config['DEMO_LOGIN_ENABLED']
        app.config['DEMO_LOGIN_ENABLED'] = False
        try:
            session = self.client.get('/api/session').get_json()
            self.assertFalse(session['demo_login_enabled'])
        finally:
            app.config['DEMO_LOGIN_ENABLED'] = previous

    def test_sqlite_uses_wal_and_waits_for_lock_contention(self):
        conn = db.get_conn()
        try:
            self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            self.assertEqual(conn.execute('PRAGMA busy_timeout').fetchone()[0], 30000)
        finally:
            conn.close()

    def test_session_persists_and_logout_revokes_access(self):
        self.assertEqual(self.login('family').status_code, 200)
        self.assertEqual(self.client.get('/api/session').get_json()['user']['username'], 'family_demo')
        self.assertEqual(self.client.get('/api/family/overview').status_code, 200)
        self.assertEqual(self.client.get('/api/alerts').status_code, 403)
        self.assertEqual(self.client.post('/api/sos').status_code, 403)
        self.client.delete('/api/session')
        self.assertEqual(self.client.get('/api/family/overview').status_code, 401)

    def test_volunteer_cannot_process_another_task(self):
        self.login('community')
        aid = self.client.post('/api/simulator/trigger', json={'scenario': 'fall'}).get_json()['alert_id']
        self.client.post(f'/api/alerts/{aid}/dispatch', json={'assignee': '王芳'})
        self.login('volunteer')
        self.assertEqual(self.client.post(f'/api/alerts/{aid}/process', json={}).status_code, 403)
        self.assertEqual(self.client.post(f'/api/alerts/{aid}/dispatch', json={'assignee': '赵敏'}).status_code, 403)
        self.assertNotIn(aid, [t['id'] for t in self.client.get('/api/volunteer/tasks').get_json()['tasks']])

    def test_legacy_role_cookie_does_not_authorize(self):
        with self.client.session_transaction() as sess:
            sess['role'] = 'community'
        self.assertEqual(self.client.get('/api/alerts').status_code, 401)
