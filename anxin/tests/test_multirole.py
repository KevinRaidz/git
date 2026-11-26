import os
import tempfile
import unittest
from datetime import datetime, timedelta

import admin_api
import care
import db
from app import app


class MultiRoleAccessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp.name, 'multi-role.db')
        db.init_db()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def login(self, role):
        username = 'admin_demo' if role == 'superadmin' else role + '_demo'
        response = self.client.post('/api/session', json={
            'username': username, 'password': 'Anxin2026!', 'role': role,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_superadmin_and_community_data_scope(self):
        db.execute('UPDATE elders SET community_id=2 WHERE id=2')
        db.execute('UPDATE devices SET community_id=2 WHERE elder_id=2')
        self.login('community')
        ids = [item['id'] for item in self.client.get('/api/admin/elders').get_json()['elders']]
        self.assertIn(1, ids)
        self.assertNotIn(2, ids)
        self.assertEqual(self.client.get('/api/admin/elders/2').status_code, 404)
        self.assertTrue(all(item['community_id'] == 1 for item in self.client.get('/api/admin/devices').get_json()['devices']))
        self.login('superadmin')
        self.assertEqual(self.client.get('/api/session').get_json()['home'], '/admin/console')
        self.assertEqual(len(self.client.get('/api/admin/elders').get_json()['elders']), 24)
        self.assertEqual(self.client.get('/api/admin/elders/2').status_code, 200)
        self.assertEqual(self.client.put('/api/admin/roles/community/scope', json={'scope': 'community'}).status_code, 200)
        self.client.delete('/api/session')
        self.login('community')
        ids = [item['id'] for item in self.client.get('/api/admin/elders').get_json()['elders']]
        self.assertEqual(len(ids), 23)
        self.assertNotIn(2, ids)

    def test_family_can_only_read_bound_elders(self):
        db.execute('UPDATE elders SET community_id=2 WHERE id=2')
        self.login('family')
        self.assertEqual(self.client.get('/api/family/overview?elder_id=1').status_code, 200)
        self.assertEqual(self.client.get('/api/family/overview?elder_id=2').status_code, 403)
        self.assertEqual(self.client.post('/api/care/notices/1/read').status_code, 404)

    def test_volunteer_service_tasks_are_account_bound(self):
        self.login('community')
        created = self.client.post('/api/admin/users', json={
            'username': 'second_volunteer', 'name': '周宁', 'role': 'volunteer', 'password': 'AnotherPass2026!',
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        other_id = created.get_json()['user']['id']
        volunteer_id = db.query_one("SELECT id FROM users WHERE username='volunteer_demo'")['id']
        service = self.client.post('/api/admin/services', json={
            'elder_id': 1, 'category': 'visit', 'title': '上门探访', 'assignee_id': volunteer_id,
        })
        self.assertEqual(service.status_code, 201, service.get_json())
        service_id = service.get_json()['service']['id']
        self.client.delete('/api/session')
        self.login('volunteer')
        my_services = self.client.get('/api/admin/services').get_json()['services']
        self.assertIn(service_id, [item['id'] for item in my_services])
        self.assertEqual(self.client.post(f'/api/admin/services/{service_id}/arrival').status_code, 200)
        self.assertEqual(self.client.post(f'/api/admin/services/{service_id}/complete', json={'receipt': '已到场，完成探访'}).status_code, 200)
        self.client.delete('/api/session')
        self.client.post('/api/session', json={'username': 'second_volunteer', 'password': 'AnotherPass2026!', 'role': 'volunteer'})
        self.assertEqual(self.client.post(f'/api/admin/services/{service_id}/arrival').status_code, 404)

    def test_messages_logs_and_passwords(self):
        self.login('community')
        created = self.client.post('/api/admin/users', json={
            'username': 'family_new', 'name': '陈女士', 'role': 'family', 'password': 'SecretPass2026!',
        })
        self.assertEqual(created.status_code, 201)
        message = self.client.post('/api/admin/messages', json={
            'role': 'family', 'title': '探访安排', 'body': '周五上午到访', 'category': 'service',
        })
        self.assertEqual(message.status_code, 201)
        logs = self.client.get('/api/admin/audit-logs').get_json()['logs']
        create_log = next(item for item in logs if item['action'] == 'POST admin_api.users')
        self.assertTrue(create_log['success'])
        self.assertNotIn('SecretPass2026!', create_log['after_json'])
        family = db.query_one("SELECT id FROM users WHERE username='family_demo'")
        self.assertIsNotNone(db.query_one('SELECT id FROM user_messages WHERE user_id=?', (family['id'],)))
        self.client.delete('/api/session')
        self.login('family')
        received = self.client.get('/api/admin/messages').get_json()['messages']
        self.assertEqual(received[0]['title'], '探访安排')
        self.assertEqual(self.client.post(f"/api/admin/messages/{received[0]['id']}/read").status_code, 200)
        self.assertEqual(self.client.get('/api/admin/audit-logs').status_code, 403)

    def test_profile_password_is_hashed_and_permissions_are_enforced(self):
        self.login('community')
        response = self.client.patch('/api/profile', json={'name': '王芳管理员', 'phone': '13800001111'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('password_hash', response.get_json()['user'])
        self.assertEqual(self.client.post('/api/profile/password', json={
            'current_password': 'Anxin2026!', 'new_password': 'ChangedPass2026!',
        }).status_code, 200)
        saved = db.query_one("SELECT password_hash FROM users WHERE username='community_demo'")['password_hash']
        self.assertNotEqual(saved, 'ChangedPass2026!')
        self.login('superadmin')
        self.assertEqual(self.client.put('/api/admin/roles/superadmin/permissions', json={'permissions': []}).status_code, 400)
        self.assertEqual(self.client.put('/api/admin/roles/community/permissions', json={'permissions': ['profile.read']}).status_code, 200)
        self.client.delete('/api/session')
        self.assertEqual(self.client.post('/api/session', json={
            'username': 'community_demo', 'password': 'ChangedPass2026!', 'role': 'community',
        }).status_code, 200)
        self.assertEqual(self.client.get('/api/admin/elders').status_code, 403)

    def test_role_scopes_cannot_be_widened(self):
        db.execute('UPDATE elders SET community_id=2 WHERE id=2')
        self.login('superadmin')
        self.assertEqual(self.client.put('/api/admin/roles/community/scope', json={'scope': 'all'}).status_code, 400)
        db.execute("UPDATE role_scopes SET scope='all' WHERE role IN ('community','family')")
        self.client.delete('/api/session')
        self.login('community')
        self.assertEqual(self.client.get('/api/admin/elders/2').status_code, 404)
        self.client.delete('/api/session')
        self.login('family')
        self.assertEqual(self.client.get('/api/family/overview?elder_id=2').status_code, 403)

    def test_notification_templates_are_scoped_and_manageable(self):
        self.login('community')
        response = self.client.post('/api/admin/notification-templates', json={
            'name': 'Community visit', 'audience_role': 'family', 'title': 'Visit update',
            'body': 'A visit has been scheduled.', 'category': 'service',
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        template_id = response.get_json()['template']['id']
        self.assertIn(template_id, [item['id'] for item in self.client.get('/api/admin/notification-templates').get_json()['templates']])
        db.execute('UPDATE notification_templates SET community_id=2 WHERE id=?', (template_id,))
        self.assertNotIn(template_id, [item['id'] for item in self.client.get('/api/admin/notification-templates').get_json()['templates']])
        self.assertEqual(self.client.patch(f'/api/admin/notification-templates/{template_id}', json={'title': 'Changed'}).status_code, 404)
        self.client.delete('/api/session')
        self.login('volunteer')
        self.assertEqual(self.client.get('/api/admin/notification-templates').status_code, 403)

    def test_simulated_device_readings_have_scoped_history(self):
        care.assess({'readings': {'water': 95, 'door': 8, 'inactive_hours': 1, 'device_online': True, 'away': False}}, elder_id=1)
        water_device = db.query_one("SELECT id FROM devices WHERE elder_id=1 AND type='water'")
        self.assertEqual(db.query_one('SELECT COUNT(*) AS n FROM device_readings WHERE device_id=?', (water_device['id'],))['n'], 1)
        self.login('community')
        history = self.client.get(f"/api/admin/devices/{water_device['id']}")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()['history'][0]['unit'], 'L')
        db.execute('UPDATE elders SET community_id=2 WHERE id=2')
        db.execute('UPDATE devices SET community_id=2 WHERE elder_id=2')
        other_device = db.query_one('SELECT id FROM devices WHERE elder_id=2 LIMIT 1')
        self.assertEqual(self.client.get(f"/api/admin/devices/{other_device['id']}").status_code, 404)

    def test_service_assignment_must_match_elder_community(self):
        self.login('superadmin')
        volunteer = self.client.post('/api/admin/users', json={
            'username': 'community_two_volunteer', 'name': 'Worker Two', 'role': 'volunteer',
            'password': 'StrongPass2026!', 'community_id': 2,
        })
        self.assertEqual(volunteer.status_code, 201, volunteer.get_json())
        other_id = volunteer.get_json()['user']['id']
        rejected = self.client.post('/api/admin/services', json={
            'elder_id': 1, 'category': 'visit', 'title': 'Cross-community task', 'assignee_id': other_id,
        })
        self.assertEqual(rejected.status_code, 403)
        valid = self.client.post('/api/admin/services', json={
            'elder_id': 1, 'category': 'visit', 'title': 'Local task',
            'assignee_id': db.query_one("SELECT id FROM users WHERE username='volunteer_demo'")['id'],
        })
        self.assertEqual(valid.status_code, 201, valid.get_json())
        service_id = valid.get_json()['service']['id']
        self.assertEqual(self.client.patch(f'/api/admin/services/{service_id}', json={'assignee_id': other_id}).status_code, 403)

    def test_automatic_backup_schedule_creates_and_logs_backup(self):
        self.login('superadmin')
        original_backup_dir = admin_api.BACKUP_DIR
        admin_api.BACKUP_DIR = os.path.join(self.temp.name, 'backups')
        try:
            old = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
            db.execute("UPDATE system_config SET value=? WHERE key='last_auto_backup_at'", (old,))
            db.execute("UPDATE system_config SET value='' WHERE key='last_auto_backup_attempt_at'")
            self.assertEqual(self.client.patch('/api/admin/config', json={'backup_interval_hours': 0}).status_code, 400)
            filename = admin_api.automatic_backup_if_due()
            self.assertTrue(filename)
            self.assertTrue(os.path.isfile(os.path.join(admin_api.BACKUP_DIR, filename)))
            self.assertIsNone(admin_api.automatic_backup_if_due())
            self.assertEqual(self.client.get('/api/admin/backups').get_json()['schedule']['interval_hours'], 24)
            self.assertIsNotNone(db.query_one("SELECT id FROM audit_logs WHERE action='automatic_backup' AND success=1"))
        finally:
            admin_api.BACKUP_DIR = original_backup_dir


if __name__ == '__main__':
    unittest.main()
