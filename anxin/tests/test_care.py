import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

import care
import db
from app import app


class CareWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp.name, 'isolated.db')
        db.init_db()
        self.client = app.test_client()
        self.login_as('community')

    def login_as(self, role):
        response = self.client.post('/api/session', json={'username': role + '_demo', 'password': 'Anxin2026!', 'role': role})
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    def trigger(self, scenario='fall'):
        response = self.client.post('/api/simulator/trigger', json={'scenario': scenario})
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_offline_away_normal_do_not_create_alerts(self):
        before = db.query_one('SELECT COUNT(*) n FROM alerts')['n']
        for scenario in ('door_stuck', 'away', 'normal'):
            self.assertIsNone(self.trigger(scenario)['alert_id'])
        self.assertEqual(db.query_one('SELECT COUNT(*) n FROM alerts')['n'], before)
        self.assertEqual(db.query_one('SELECT COUNT(*) n FROM care_samples')['n'], 3)

    def test_personal_baseline_changes_decision(self):
        db.execute('UPDATE readings SET water=10 WHERE elder_id=1 AND water>0')
        sample = dict(water=5, door=0, inactive_hours=12, device_online=True, away=False)
        result = care.assess({'readings': sample})
        self.assertEqual(result['baseline'], 10)
        self.assertIsNone(result['alert_id'])
        sample['water'] = 1
        self.assertEqual(care.assess({'readings': sample})['level'], 'red')

    def test_duplicate_and_higher_risk_merge(self):
        first = self.trigger('no_water')
        second = self.trigger()
        self.assertEqual(first['alert_id'], second['alert_id'])
        self.assertTrue(second['merged'])
        self.assertEqual(db.query_one('SELECT level FROM alerts WHERE id=?', (first['alert_id'],))['level'], 'red')

    def test_flow_notices_read_receipt_and_risk(self):
        aid = self.trigger()['alert_id']
        self.assertEqual(self.client.post(f'/api/alerts/{aid}/close', json={'result': '跳步'}).status_code, 409)
        self.login_as('elder')
        self.assertEqual(self.client.post('/api/checkin').status_code, 200)
        self.login_as('community')
        self.assertEqual(db.query_one('SELECT risk_level FROM elders WHERE id=1')['risk_level'], 'red')
        for action, body in [('dispatch', {'assignee': '赵敏'}), ('process', {}), ('close', {'result': '已确认安全'})]:
            self.assertEqual(self.client.post(f'/api/alerts/{aid}/{action}', json=body).status_code, 200)
        row = db.query_one('SELECT * FROM alerts WHERE id=?', (aid,))
        self.assertEqual(row['result'], '已确认安全')
        self.assertEqual(db.query_one('SELECT risk_level FROM elders WHERE id=1')['risk_level'], 'green')
        self.assertEqual(len(care.enrich(row)['timeline']), 4)
        self.login_as('family')
        notices = self.client.get('/api/family/overview').get_json()['notices']
        self.assertEqual(len(notices), 4)
        nid = notices[0]['id']
        self.assertEqual(self.client.post(f'/api/care/notices/{nid}/read').status_code, 200)
        self.assertIsNotNone(db.query_one('SELECT read_at FROM care_notices WHERE id=?', (nid,))['read_at'])

    def test_concurrent_dispatch_only_one_succeeds(self):
        aid = self.trigger()['alert_id']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda who: care.transition(aid, 'dispatch', {'assignee': who})[1], ['赵敏', '王芳']))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(db.query_one("SELECT COUNT(*) n FROM care_logs WHERE alert_id=? AND action='已安排跟进'", (aid,))['n'], 1)

    def test_timeout_notices_once_per_phase_and_no_closed_escalation(self):
        aid = self.trigger()['alert_id']
        db.execute("UPDATE care_cases SET due_at='2000-01-01 00:00:00' WHERE alert_id=?", (aid,))
        self.assertEqual(care.scan_due(), 1)
        self.assertEqual(care.scan_due(), 0)
        self.assertTrue(care.enrich(db.query_one('SELECT * FROM alerts WHERE id=?', (aid,)))['escalated'])
        care.transition(aid, 'dispatch', {'assignee': '赵敏'})
        care.transition(aid, 'process', {})
        self.assertEqual(self.client.post(f'/api/alerts/{aid}/close', json={'result': ''}).status_code, 400)
        care.transition(aid, 'close', {'result': '已核实'})
        db.execute("UPDATE care_cases SET due_at='2000-01-01 00:00:00' WHERE alert_id=?", (aid,))
        self.assertEqual(care.scan_due(), 0)

    def test_validation_and_missing_case(self):
        self.assertEqual(self.client.post('/api/simulator/trigger', json={'readings': {'water': -1}}).status_code, 400)
        self.assertEqual(self.client.post('/api/alerts/99999/process', json={}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
