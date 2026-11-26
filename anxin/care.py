"""可解释预警、工单流转与站内通知。设备输入仅用于本地演示。"""
import json
import threading
from datetime import datetime, timedelta

import db


def stamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def init_schema(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS care_cases (
        alert_id INTEGER PRIMARY KEY, evidence TEXT NOT NULL,
        due_at TEXT NOT NULL, escalated_at TEXT, source_key TEXT
    );
    CREATE TABLE IF NOT EXISTS care_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL,
        ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS care_notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alert_id INTEGER NOT NULL,
        role TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        created_at TEXT NOT NULL, read_at TEXT
    );
    CREATE TABLE IF NOT EXISTS care_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT, elder_id INTEGER NOT NULL,
        created_at TEXT NOT NULL, payload TEXT NOT NULL, decision TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_care_logs_alert ON care_logs(alert_id, id);
    CREATE INDEX IF NOT EXISTS idx_care_notices_role ON care_notices(role, id);
    ''')


def log(conn, aid, actor, action, detail):
    conn.execute('INSERT INTO care_logs(alert_id,ts,actor,action,detail) VALUES(?,?,?,?,?)',
                 (aid, stamp(), actor, action, detail))


def notify(conn, aid, title, body, roles=('family', 'community')):
    target = conn.execute('''SELECT a.elder_id,a.assignee_user_id,e.community_id FROM alerts a
                             JOIN elders e ON e.id=a.elder_id WHERE a.id=?''', (aid,)).fetchone()
    for role in roles:
        conn.execute('INSERT INTO care_notices(alert_id,role,title,body,created_at) VALUES(?,?,?,?,?)',
                     (aid, role, title, body, stamp()))
        if not target:
            continue
        if role == 'family':
            recipients = []
        elif role == 'community':
            recipients = conn.execute("SELECT id FROM users WHERE status='active' AND role='community' AND community_id=?",
                                      (target['community_id'],)).fetchall()
        elif role == 'volunteer' and target['assignee_user_id']:
            recipients = conn.execute("SELECT id FROM users WHERE id=? AND role='volunteer' AND status='active'",
                                      (target['assignee_user_id'],)).fetchall()
        else:
            recipients = []
        conn.executemany('''INSERT INTO user_messages(user_id,audience_role,community_id,title,body,category,created_at)
                            VALUES(?,?,?,?,?,'alert',?)''',
                         [(user['id'], role, target['community_id'], title, body, stamp()) for user in recipients])


def recompute_risk(conn, elder_id):
    row = conn.execute("SELECT level FROM alerts WHERE elder_id=? AND status!='closed' "
                       "ORDER BY CASE level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END LIMIT 1",
                       (elder_id,)).fetchone()
    conn.execute('UPDATE elders SET risk_level=? WHERE id=?', (row['level'] if row else 'green', elder_id))


def create_case(conn, elder_id, level, trigger, reason, evidence, source_key):
    existing = conn.execute("SELECT a.id,a.code FROM alerts a JOIN care_cases c ON c.alert_id=a.id WHERE a.elder_id=? AND a.trigger_type=? AND a.status!='closed' ORDER BY a.id DESC LIMIT 1",
                            (elder_id, trigger)).fetchone()
    if existing:
        log(conn, existing['id'], '规则引擎', '重复信号合并', '相同类型的异常仍在处理中，本次未重复派单。')
        return existing['id'], True
    ts = stamp()
    aid = conn.execute("INSERT INTO alerts(elder_id,level,trigger_type,reason,created_at,status) VALUES(?,?,?,?,?,'pending')",
                       (elder_id, level, trigger, reason, ts)).lastrowid
    code = f"AX-{datetime.now():%Y%m%d}-{aid:05d}"
    conn.execute('UPDATE alerts SET code=? WHERE id=?', (code, aid))
    minutes = 5 if level == 'red' else 30
    due = (datetime.now() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('INSERT INTO care_cases(alert_id,evidence,due_at,source_key) VALUES(?,?,?,?)',
                 (aid, json.dumps(evidence, ensure_ascii=False), due, source_key))
    log(conn, aid, '规则引擎' if source_key != 'sos' else '老人本人', '发现异常', reason)
    notify(conn, aid, '新的安全关注', f'{code}：{reason}。请社区在 {minutes} 分钟内安排跟进。')
    recompute_risk(conn, elder_id)
    return aid, False


PRESETS = {
    'fall': dict(water=0, door=0, inactive_hours=12, device_online=True, away=False),
    'no_water': dict(water=0, door=1, inactive_hours=6, device_online=True, away=False),
    'door_stuck': dict(water=0, door=0, inactive_hours=36, device_online=False, away=False),
    'normal': dict(water=95, door=8, inactive_hours=1, device_online=True, away=False),
    'away': dict(water=0, door=0, inactive_hours=12, device_online=True, away=True),
}


def assess(payload, elder_id=1):
    if not isinstance(payload, dict):
        raise ValueError('请提交有效的读数对象')
    scenario = payload.get('scenario', 'custom')
    sample = payload.get('readings', PRESETS.get(scenario))
    if not isinstance(sample, dict):
        raise ValueError('请选择场景或填写完整的设备读数')
    clean = {}
    for key, maximum in [('water', 2000), ('door', 300), ('inactive_hours', 168)]:
        value = sample.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= maximum:
            raise ValueError('读数不完整或超出允许范围')
        clean[key] = value
    for key in ('device_online', 'away'):
        if not isinstance(sample.get(key), bool):
            raise ValueError('请确认设备和外出状态')
        clean[key] = sample[key]
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        baseline = conn.execute('SELECT AVG(water) AS n FROM readings WHERE elder_id=? AND day<? AND water>0',
                                (elder_id, datetime.now().strftime('%Y-%m-%d'))).fetchone()['n']
        baseline = round(baseline or 100, 1)
        evidence = [
            f"今日累计用水 {clean['water']} L，历史有效日均值 {baseline} L",
            f"门磁开合 {clean['door']} 次，连续无活动 {clean['inactive_hours']} 小时",
            '设备在线' if clean['device_online'] else '设备离线，当前读数可信度不足',
            '已登记外出（演示输入）' if clean['away'] else '未登记外出',
        ]
        level, trigger = None, None
        if not clean['device_online']:
            title, rule = '先检查设备，不生成安全预警', '设备离线：无法根据缺失数据判断老人状态，建议人工确认设备。'
        elif clean['away']:
            title, rule = '已登记外出，暂不生成预警', '外出状态生效：本次居家活动缺失不触发自动预警，主动 SOS 仍有效。'
        elif clean['inactive_hours'] >= 12 and clean['door'] == 0 and clean['water'] < baseline * .2:
            title, rule = '发现红色关注，需要尽快核实', '连续无活动 ≥ 12 小时，且门磁为 0、用水低于历史均值的 20%。'
            level, trigger = 'red', 'inactivity_rule'
        elif clean['inactive_hours'] >= 6 and clean['door'] <= 1 and clean['water'] < baseline * .2:
            title, rule = '发现黄色关注，建议联系确认', '连续无活动 ≥ 6 小时，且门磁 ≤ 1、用水低于历史均值的 20%。'
            level, trigger = 'yellow', 'inactivity_rule'
        else:
            title, rule = '本次读数未触发预警', '未满足多信号联合规则，单一低用水不直接判为异常。'
        aid, merged = None, False
        if level:
            # 已有同类工单时合并；更严重的新信号提升等级并重新限定响应时间。
            aid, merged = create_case(conn, elder_id, level, trigger, title, evidence + [rule], scenario)
            if merged and level == 'red':
                current = conn.execute('SELECT level FROM alerts WHERE id=?', (aid,)).fetchone()
                if current['level'] != 'red':
                    conn.execute("UPDATE alerts SET level='red',reason=? WHERE id=?", (title, aid))
                    conn.execute('UPDATE care_cases SET evidence=?,due_at=?,escalated_at=NULL WHERE alert_id=?',
                                 (json.dumps(evidence + [rule], ensure_ascii=False),
                                  (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'), aid))
                    log(conn, aid, '规则引擎', '风险升级', '新的联合信号满足红色规则，响应期限缩短为 5 分钟。')
                    notify(conn, aid, '风险升级，请尽快核实', title)
                    recompute_risk(conn, elder_id)
        result = dict(ok=True, title=title, msg=rule, evidence=evidence, level=level,
                      alert_id=aid, merged=merged, sample=clean, baseline=baseline,
                      disclaimer='模拟设备数据；规则仅用于流程演示，未经真实场景安全有效性验证。')
        conn.execute('INSERT INTO care_samples(elder_id,created_at,payload,decision) VALUES(?,?,?,?)',
                     (elder_id, stamp(), json.dumps(clean), json.dumps(result, ensure_ascii=False)))
        if clean['device_online']:
            readings = {
                'water': (clean['water'], 'L'),
                'door': (clean['door'], '次'),
                'motion': (max(0, 24 - clean['inactive_hours']), 'h'),
            }
            for device in conn.execute('''SELECT id,type FROM devices
                                          WHERE elder_id=? AND archived_at IS NULL AND status!='inactive' ''',
                                       (elder_id,)).fetchall():
                reading = readings.get(device['type'])
                if reading is None:
                    continue
                value, unit = reading
                conn.execute('INSERT INTO device_readings(device_id,value,unit,recorded_at) VALUES(?,?,?,?)',
                             (device['id'], value, unit, stamp()))
                conn.execute('UPDATE devices SET last_reading=?,updated_at=? WHERE id=?',
                             (f'{value:g} {unit}', stamp(), device['id']))
        conn.commit()
        return result
    finally:
        conn.close()


def transition(aid, action, data):
    if not isinstance(data, dict):
        return dict(ok=False, message='请提交有效的操作参数'), 400
    required, target = {'dispatch': ('pending', 'dispatched'), 'process': ('dispatched', 'processing'),
                        'close': ('processing', 'closed')}[action]
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM alerts WHERE id=?', (aid,)).fetchone()
        if not row:
            return dict(ok=False, message='工单不存在'), 404
        if row['status'] != required:
            return dict(ok=False, message='工单已被更新，请刷新后按顺序操作'), 409
        ts = stamp()
        if action == 'dispatch':
            who = data.get('assignee', '赵敏')
            assigned_user_id = data.get('assignee_user_id')
            if assigned_user_id:
                assigned = conn.execute("SELECT id,name FROM users WHERE id=? AND role='volunteer' AND status='active'", (assigned_user_id,)).fetchone()
                if not assigned:
                    return dict(ok=False, message='请选择有效的志愿者账号'), 400
                who, role, assigned_user_id = assigned['name'], 'volunteer', assigned['id']
            else:
                assigned = conn.execute("SELECT id FROM users WHERE name=? AND role='volunteer' AND status='active' LIMIT 1", (who,)).fetchone()
                assigned_user_id = assigned['id'] if assigned else None
                role = 'volunteer' if assigned else {'王芳': 'worker', '物业老周': 'property'}.get(who)
            if not role:
                return dict(ok=False, message='请选择有效负责人'), 400
            conn.execute('UPDATE alerts SET status=?,assignee=?,assignee_role=?,assignee_user_id=? WHERE id=?',
                         (target, who, role, assigned_user_id, aid))
            actor, label, detail = data.get('actor_name', '社区值班员'), '已安排跟进', f'已派给 {who}，等待到场确认。'
        elif action == 'process':
            conn.execute('UPDATE alerts SET status=? WHERE id=?', (target, aid))
            actor, label, detail = data.get('actor_name') or row['assignee'] or '服务人员', '已到场处置', '服务人员确认到场，开始核实老人情况。'
        else:
            result = data.get('result', '')
            if not isinstance(result, str) or not result.strip() or len(result.strip()) > 300:
                return dict(ok=False, message='请填写 1–300 字的处置回执'), 400
            conn.execute('UPDATE alerts SET status=?,result=?,closed_at=? WHERE id=?', (target, result.strip(), ts, aid))
            actor, label, detail = data.get('actor_name') or row['assignee'] or '服务人员', '服务已完成', result.strip()
        minutes = 15 if action == 'dispatch' else 30
        if action != 'close':
            conn.execute('UPDATE care_cases SET due_at=?,escalated_at=NULL WHERE alert_id=?',
                         ((datetime.now() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S'), aid))
        log(conn, aid, actor, label, detail)
        roles = ('family', 'community', 'volunteer') if action == 'dispatch' else ('family', 'community')
        notify(conn, aid, label, f"{row['code']}：{detail}", roles)
        recompute_risk(conn, row['elder_id'])
        conn.commit()
        return dict(ok=True), 200
    finally:
        conn.close()


def scan_due():
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute("SELECT a.id,a.code,a.assignee FROM alerts a JOIN care_cases c ON c.alert_id=a.id "
                            "WHERE a.status!='closed' AND c.escalated_at IS NULL AND c.due_at<=?", (stamp(),)).fetchall()
        for row in rows:
            conn.execute('UPDATE care_cases SET escalated_at=? WHERE alert_id=?', (stamp(), row['id']))
            detail = f"{row['code']} 超过本阶段响应期限，已提醒社区值班员跟进。"
            log(conn, row['id'], '超时巡检', '超时催办', detail)
            notify(conn, row['id'], '超时未完成，请跟进', detail)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def enrich(alert):
    item = dict(alert)
    case = db.query_one('SELECT * FROM care_cases WHERE alert_id=?', (item['id'],))
    item.update(evidence=json.loads(case['evidence']) if case else ['历史演示工单，未保存原始触发读数。'],
                due_at=case['due_at'] if case else None,
                escalated=bool(case and case['escalated_at'] and item['status'] != 'closed'),
                timeline=[dict(r) for r in db.query('SELECT * FROM care_logs WHERE alert_id=? ORDER BY id', (item['id'],))])
    return item


def start_monitor():
    def run():
        while True:
            threading.Event().wait(15)
            try:
                scan_due()
            except Exception:
                import logging
                logging.exception('超时巡检失败，将在下一轮重试')
    threading.Thread(target=run, daemon=True, name='care-deadline-monitor').start()
