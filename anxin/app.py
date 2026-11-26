# -*- coding: utf-8 -*-
"""
安芯 · 独居老人安全守护与社区关爱平台（本地演示）
=========================================================
运行方式（PyCharm）：
  1. pip install -r requirements.txt
  2. 右键运行本文件（或终端执行 python app.py）
  3. 浏览器打开 http://127.0.0.1:5000

技术栈：React + Vite + Flask + SQLite + ECharts
页面清单见 README.md
"""
import os
import secrets
from datetime import datetime, timedelta

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash

import db
import care
import access_control as access
from admin_api import bp as admin_api, start_backup_monitor

app = Flask(__name__)
app.secret_key = os.environ.get('ANXIN_SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', PERMANENT_SESSION_LIFETIME=timedelta(hours=8))

DEMO_ELDER_ID = 1  # 演示主角：张桂芳（82 岁独居，儿子李伟在上海）

LEVEL_TEXT = {"green": "平安", "yellow": "需关注", "red": "紧急"}
STATUS_TEXT = {"pending": "待核实", "dispatched": "已派单", "processing": "处置中", "closed": "已归档"}
ROLE_TEXT = {"elder": "老人", "family": "子女", "community": "社区", "volunteer": "志愿者"}
ROLE_TEXT['superadmin'] = '超级管理员'
ROLE_HOME = {
    "superadmin": "/admin/console",
    "elder": "/elder/home",
    "family": "/family/overview",
    "community": "/community/alerts",
    "volunteer": "/volunteer/tasks",
}
REACT_DIST = os.path.join(app.static_folder, "react")
app.register_blueprint(admin_api)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


# ---------------------------------------------------------------- 会话与 React 页面入口
@app.route("/login")
def login():
    return send_from_directory(REACT_DIST, "index.html")


def current_account():
    uid = session.get('user_id')
    row = db.query_one('SELECT id,username,name,role,status,community_id,elder_id,phone FROM users WHERE id=?', (uid,)) if uid else None
    return dict(row) if row else None


@app.before_request
def protect_api():
    path = request.path
    if not path.startswith('/api/') or path == '/api/session':
        return None
    user = current_account()
    if user and user['status'] != 'active':
        session.clear()
        user = None
    if not user:
        return jsonify(ok=False, message='请先登录后再操作'), 401
    g.account = user
    if user['status'] != 'active':
        session.clear()
        return jsonify(ok=False, message='账号已停用，请联系管理员'), 401
    permission = access.endpoint_permission(request.endpoint, request.method)
    if not permission:
        return jsonify(ok=False, message='接口不存在'), 404
    if request.endpoint in {'api_alert_dispatch', 'api_alert_process', 'api_alert_close'}:
        alert_id = request.view_args.get('aid') if request.view_args else None
        if not access.alert_accessible(user, alert_id):
            if user['role'] == 'volunteer' and alert_id and db.query_one('SELECT id FROM alerts WHERE id=?', (alert_id,)):
                return jsonify(ok=False, message='只能处理分配给自己的任务'), 403
            return jsonify(ok=False, message='工单不存在或不在数据范围内'), 404
    if access.permission_allowed(user, permission):
        g.api_permission = permission
        return None
    if (user['role'] == 'volunteer' and request.endpoint in {'api_alert_process', 'api_alert_close'}
            and access.permission_allowed(user, 'volunteer.task.write')):
        try:
            alert_id = int(request.view_args['aid'])
        except (KeyError, TypeError, ValueError):
            return jsonify(ok=False, message='工单地址无效'), 404
        if not access.alert_accessible(user, alert_id):
            return jsonify(ok=False, message='只能处理分配给自己的任务'), 403
        g.api_permission = 'volunteer.task.write'
        return None
    if user['role'] == 'volunteer' and path.startswith('/api/alerts/'):
        parts = path.split('/')
        if len(parts) == 5 and parts[3].isdigit():
            if not access.alert_accessible(user, int(parts[3])):
                return jsonify(ok=False, message='只能处理分配给自己的任务'), 403
    return jsonify(ok=False, message='当前账号没有此操作权限'), 403


@app.after_request
def audit_api_write(response):
    user = getattr(g, 'account', None)
    if (request.path.startswith('/api/') and request.path != '/api/session'
            and (request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
                 or (request.method == 'GET' and (request.path.startswith('/api/admin/export/')
                                                   or request.path.startswith('/api/admin/backups/'))))
            and user):
        payload = access.sanitize_payload(request.get_json(silent=True) or {})
        if request.files:
            payload['files'] = [item.filename for item in request.files.values()]
        endpoint = request.endpoint or request.path
        module = request.path.split('/')[2] if len(request.path.split('/')) > 2 else 'system'
        action = f'{request.method} {endpoint}'
        access.audit(user, module, action, request.path, response.status_code < 400,
                     response.get_json(silent=True).get('message', '') if response.status_code >= 400 and response.is_json else '',
                     getattr(g, 'audit_before', {}), payload, request.remote_addr or '')
    return response


def audit_login(username, success, failure_reason=''):
    user = db.query_one('SELECT id,name,role,community_id FROM users WHERE username=?', (username or '',))
    db.execute('''INSERT INTO audit_logs(user_id,operator,role,community_id,created_at,module,action,
                  object_ref,before_json,after_json,success,failure_reason,ip)
                  VALUES(?,?,?,?,datetime('now','localtime'),'session','login',?,'','',?,?,?)''',
               (user['id'] if user else None, user['name'] if user else (username or 'unknown'),
                user['role'] if user else 'unknown', user['community_id'] if user else None,
                username or 'unknown', int(success), failure_reason, request.remote_addr or ''))


@app.route('/api/profile', methods=['GET', 'PATCH'])
def profile():
    if request.method == 'GET':
        return jsonify(user=g.account)
    data = request.get_json(silent=True) or {}
    name = data.get('name', g.account['name'])
    phone = data.get('phone', g.account.get('phone', ''))
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or not isinstance(phone, str) or len(phone) > 40:
        return jsonify(ok=False, message='姓名或联系电话格式无效'), 400
    g.audit_before = {'name': g.account['name'], 'phone': g.account.get('phone', '')}
    db.execute('UPDATE users SET name=?,phone=?,updated_at=? WHERE id=?',
               (name.strip(), phone.strip(), now_str(), g.account['id']))
    return jsonify(ok=True, user=current_account())


@app.route('/api/profile/password', methods=['POST'])
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get('current_password', '')
    new = data.get('new_password', '')
    stored = db.query_one('SELECT password_hash FROM users WHERE id=?', (g.account['id'],))
    if not check_password_hash(stored['password_hash'], current):
        return jsonify(ok=False, message='当前密码不正确'), 400
    minimum = int((db.query_one("SELECT value FROM system_config WHERE key='password_min_length'") or {'value': '10'})['value'])
    if not isinstance(new, str) or len(new) < minimum or len(new) > 200:
        return jsonify(ok=False, message=f'新密码至少 {minimum} 位'), 400
    from werkzeug.security import generate_password_hash
    db.execute('UPDATE users SET password_hash=?,updated_at=? WHERE id=?',
               (generate_password_hash(new), now_str(), g.account['id']))
    return jsonify(ok=True)


@app.route("/api/session", methods=["GET", "POST", "DELETE"])
def api_session():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict) or not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
            return jsonify(ok=False, message='请输入账号和密码'), 400
        username, password = data['username'].strip(), data['password']
        if not username or not password or len(username) > 80 or len(password) > 200:
            return jsonify(ok=False, message='请输入有效的账号和密码'), 400
        user = db.query_one('SELECT * FROM users WHERE username=?', (username,))
        if not user or not check_password_hash(user['password_hash'], password):
            audit_login(username, False, '账号或密码错误')
            return jsonify(ok=False, message='账号或密码错误'), 401
        if user['status'] != 'active':
            audit_login(username, False, '账号已停用')
            return jsonify(ok=False, message='账号已停用，请联系管理员'), 401
        if data.get('role') and data['role'] != user['role']:
            audit_login(username, False, '身份选择与账号角色不匹配')
            return jsonify(ok=False, message='该账号不属于所选身份，请选择对应身份后登录'), 403
        session.clear()
        session['user_id'] = user['id']
        session.permanent = True
        access.audit(dict(user), 'session', 'login', username, True, '', {}, {}, request.remote_addr or '')
    elif request.method == "DELETE":
        old_user = current_account()
        session.clear()
        if old_user:
            access.audit(old_user, 'session', 'logout', old_user['username'], True, '', {}, {}, request.remote_addr or '')

    user = current_account()
    if user and user['status'] != 'active':
        session.clear()
        user = None
    role = user['role'] if user else None
    return jsonify({
        "ok": True,
        "role": role,
        "role_name": ROLE_TEXT.get(role, ""),
        "user": user,
        "permissions": access.permissions_for(role) if role else [],
        "data_scope": access.data_scope(user) if user else None,
        "home": ROLE_HOME.get(role, "/login"),
        "today": today_str(),
        "weekday": WEEKDAYS[datetime.now().weekday()],
    })


@app.route("/api/elder/home")
def api_elder_home():
    elder_id = g.account.get('elder_id')
    if not elder_id or not access.elder_accessible(g.account, elder_id):
        return jsonify(ok=False, message='此账号尚未绑定老人档案'), 404
    elder = dict(db.query_one("SELECT * FROM elders WHERE id=?", (elder_id,)))
    checked_today = bool(elder["last_checkin"] and elder["last_checkin"].startswith(today_str()))
    return jsonify({
        "elder": elder,
        "checked_today": checked_today,
        "today": today_str(),
        "weekday": WEEKDAYS[datetime.now().weekday()],
    })


@app.route("/api/family/overview")
def api_family_overview():
    linked = db.query('SELECT elder_id FROM family_links WHERE user_id=? ORDER BY id', (g.account['id'],))
    if not linked:
        return jsonify(ok=False, message='此家属账号尚未绑定老人档案'), 404
    elder_id = request.args.get('elder_id', type=int) or linked[0]['elder_id']
    if not access.elder_accessible(g.account, elder_id):
        return jsonify(ok=False, message='无权查看该老人信息'), 403
    elder = dict(db.query_one("SELECT * FROM elders WHERE id=?", (elder_id,)))
    events = db.query("SELECT * FROM events WHERE elder_id=? AND ts LIKE ? ORDER BY ts",
                      (elder_id, today_str() + "%"))
    readings = db.query("SELECT * FROM readings WHERE elder_id=? ORDER BY day", (elder_id,))
    alerts = db.query("SELECT * FROM alerts WHERE elder_id=? ORDER BY created_at DESC LIMIT 6", (elder_id,))
    alert_ids = [item['id'] for item in alerts]
    legacy_notices = []
    if alert_ids:
        placeholders = ','.join('?' for _ in alert_ids)
        legacy_notices = db.query(f"SELECT * FROM care_notices WHERE role='family' AND alert_id IN ({placeholders}) ORDER BY id DESC LIMIT 20", alert_ids)
    notices = [{**dict(item), 'notice_type': 'care'} for item in legacy_notices]
    notices.extend({**dict(item), 'notice_type': 'message'} for item in db.query(
        'SELECT * FROM user_messages WHERE user_id=? ORDER BY id DESC LIMIT 20', (g.account['id'],)))
    notices.sort(key=lambda item: item['created_at'], reverse=True)
    return jsonify({
        "elder": elder,
        "events": [dict(event) for event in events],
        "readings": [dict(reading) for reading in readings],
        "alerts": [care.enrich(alert) for alert in alerts],
        "notices": notices[:20],
        "messages": [dict(n) for n in db.query('SELECT * FROM user_messages WHERE user_id=? ORDER BY id DESC LIMIT 20', (g.account['id'],))],
    })


@app.route("/api/elders")
def api_elders():
    scope, args = access.scope_sql(g.account, 'e')
    filters = [scope, "e.status!='archived'"]
    params = list(args)
    level = request.args.get("level", "")
    if level in ("green", "yellow", "red"):
        filters.append('e.risk_level=?')
        params.append(level)
    name = request.args.get('name', '').strip()
    if name:
        filters.append('e.name LIKE ?')
        params.append(f'%{name}%')
    elders = db.query(f"""SELECT e.* FROM elders e WHERE {' AND '.join(filters)} ORDER BY
                           CASE risk_level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
                           age DESC""", params)
    needs = db.query(f"""SELECT n.*, e.name AS elder_name FROM needs n
                        JOIN elders e ON e.id=n.elder_id WHERE {scope} ORDER BY n.id""", args)
    return jsonify({
        "elders": [dict(elder) for elder in elders],
        "needs": [dict(need) for need in needs],
        "current_level": level,
    })


@app.route("/api/volunteer/tasks")
def api_volunteer_tasks():
    tasks = db.query("""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                        LEFT JOIN elders e ON e.id = a.elder_id
                        WHERE a.assignee_role = 'volunteer' AND (a.assignee_user_id=? OR (a.assignee_user_id IS NULL AND a.assignee=?))
                          AND a.status IN ('dispatched','processing')
                        ORDER BY a.level = 'red' DESC, a.created_at""", (g.account['id'], g.account['name']))
    done = db.query("""SELECT a.*, e.name AS elder_name FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       WHERE a.assignee_role = 'volunteer' AND (a.assignee_user_id=? OR (a.assignee_user_id IS NULL AND a.assignee=?))
                         AND a.status = 'closed'
                       ORDER BY a.closed_at DESC LIMIT 5""", (g.account['id'], g.account['name']))
    services = db.query('''SELECT s.*,e.name AS elder_name,e.address FROM services s
                           JOIN elders e ON e.id=s.elder_id
                           WHERE s.assignee_id=? AND s.archived_at IS NULL AND s.status IN ('planned','processing')
                           ORDER BY s.scheduled_at,s.id DESC''', (g.account['id'],))
    done_services = db.query('''SELECT s.*,e.name AS elder_name FROM services s JOIN elders e ON e.id=s.elder_id
                                WHERE s.assignee_id=? AND s.status='completed'
                                ORDER BY s.updated_at DESC LIMIT 5''', (g.account['id'],))
    return jsonify({
        "tasks": [care.enrich(task) for task in tasks],
        "done": [dict(task) for task in done],
        "services": [dict(task) for task in services],
        "done_services": [dict(task) for task in done_services],
    })


# ---------------------------------------------------------------- API
@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    """老人打卡"""
    ts = now_str()
    elder_id = g.account['elder_id']
    if not elder_id or not access.elder_accessible(g.account, elder_id):
        return jsonify(ok=False, message='此账号尚未绑定老人档案'), 404
    db.execute("UPDATE elders SET last_checkin=? WHERE id=?", (ts, elder_id))
    conn = db.get_conn()
    try:
        care.recompute_risk(conn, elder_id)
        conn.commit()
    finally:
        conn.close()
    db.execute("INSERT INTO events (elder_id, ts, icon, text, kind) VALUES (?,?,?,?,?)",
               (elder_id, ts, "✅", "在「今日平安」报平安", "normal"))
    db.execute("UPDATE readings SET checkin=1 WHERE elder_id=? AND day=?", (elder_id, today_str()))
    return jsonify({"ok": True, "time": ts[-5:]})


@app.route("/api/sos", methods=["POST"])
def api_sos():
    """触发 SOS：生成红色预警并通知家属与社区"""
    conn = db.get_conn()
    elder_id = g.account.get('elder_id')
    if not elder_id or not access.elder_accessible(g.account, elder_id):
        conn.close()
        return jsonify(ok=False, message='此账号尚未绑定老人档案'), 404
    try:
        conn.execute('BEGIN IMMEDIATE')
        aid, merged = care.create_case(conn, elder_id, 'red', 'sos', '老人主动发出紧急求助',
                                       ['老人长按求助并完成倒计时确认', '主动求助优先，不受外出状态影响'], 'sos')
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "alert_id": aid, "merged": merged,
                    "notified": ["家属站内消息已保存", "社区待办已生成", "等待社区安排服务人员"]})


@app.route("/api/dashboard")
def api_dashboard():
    """驾驶舱数据（前端每 5 秒轮询）"""
    scope, scope_args = access.scope_sql(g.account, 'e')
    elders = db.query(f"SELECT id, name, age, x, y, risk_level FROM elders e WHERE {scope} AND e.status!='archived'", scope_args)
    cnt = {"green": 0, "yellow": 0, "red": 0}
    for e in elders:
        cnt[e["risk_level"]] = cnt.get(e["risk_level"], 0) + 1

    status_counts = {k: 0 for k in STATUS_TEXT}
    for a in db.query(f"SELECT a.status, COUNT(*) AS n FROM alerts a JOIN elders e ON e.id=a.elder_id WHERE {scope} GROUP BY a.status", scope_args):
        status_counts[a["status"]] = a["n"]

    recent = db.query(f"""SELECT a.*, e.name AS elder_name, e.age FROM alerts a
                         LEFT JOIN elders e ON e.id = a.elder_id
                         WHERE {scope}
                         ORDER BY a.created_at DESC LIMIT 8""", scope_args)

    # 近 24 小时预警趋势（4 小时一桶）
    trend = []
    now = datetime.now()
    for i in range(6, 0, -1):
        start = now - timedelta(hours=i * 4)
        end = now - timedelta(hours=(i - 1) * 4)
        row = db.query_one(f"""SELECT COUNT(*) AS n FROM alerts a JOIN elders e ON e.id=a.elder_id
                              WHERE {scope} AND a.created_at BETWEEN ? AND ?""",
                           [*scope_args, start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")])
        trend.append(row["n"])

    devices = db.query(f"""SELECT d.status FROM devices d JOIN elders e ON e.id=d.elder_id
                           WHERE {scope} AND d.archived_at IS NULL""", scope_args)
    devices_total = len(devices)
    devices_online = sum(1 for device in devices if device['status'] == 'online')
    return jsonify({
        "kpi": {
            "total": len(elders), "green": cnt["green"], "yellow": cnt["yellow"], "red": cnt["red"],
            "devices_online": devices_online, "devices_total": devices_total,
            "visit_done": 41, "visit_due": 50,
        },
        "points": [{"id": e["id"], "name": e["name"], "age": e["age"], "x": e["x"], "y": e["y"],
                    "level": e["risk_level"]} for e in elders],
        "recent_alerts": [{"code": a["code"], "elder": a["elder_name"], "age": a["age"], "level": a["level"],
                           "reason": a["reason"], "status": a["status"], "created_at": a["created_at"],
                           "assignee": a["assignee"]} for a in recent],
        "trend": trend,
        "status_counts": status_counts,
        "last_update": now_str(),
    })


@app.route("/api/alerts")
def api_alerts():
    """全部预警工单（预警工单页轮询）"""
    scope, args = access.scope_sql(g.account, 'e')
    rows = db.query(f"""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       WHERE {scope}
                       ORDER BY CASE a.level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
                                CASE a.status WHEN 'pending' THEN 0 WHEN 'dispatched' THEN 1
                                     WHEN 'processing' THEN 2 ELSE 3 END, a.created_at DESC""", args)
    care.scan_due()
    return jsonify({"alerts": [care.enrich(r) for r in rows]})


@app.route("/api/alerts/<int:aid>/dispatch", methods=["POST"])
def api_alert_dispatch(aid):
    data = request.get_json(silent=True) or {}
    assignee = None
    if data.get('assignee_user_id'):
        assignee = db.query_one("SELECT id,name,role,status,community_id FROM users WHERE id=?", (data['assignee_user_id'],))
    elif data.get('assignee'):
        assignee = db.query_one("SELECT id,name,role,status,community_id FROM users WHERE name=? AND role='volunteer' AND status='active' LIMIT 1", (data['assignee'],))
    if assignee and (assignee['role'] != 'volunteer' or assignee['status'] != 'active'):
        return jsonify(ok=False, message='请选择有效的志愿者账号'), 400
    if assignee and g.account['role'] != 'superadmin' and assignee['community_id'] != g.account['community_id']:
        return jsonify(ok=False, message='不能派给其他社区的志愿者'), 403
    if assignee:
        data['assignee_user_id'] = assignee['id']
        data['assignee'] = assignee['name']
    data['actor_name'] = g.account['name']
    current = db.query_one('SELECT status,assignee,assignee_role FROM alerts WHERE id=?', (aid,))
    g.audit_before = dict(current) if current else {}
    result, status = care.transition(aid, 'dispatch', data)
    return jsonify(result), status


@app.route("/api/alerts/<int:aid>/process", methods=["POST"])
def api_alert_process(aid):
    current = db.query_one('SELECT status,assignee,assignee_role FROM alerts WHERE id=?', (aid,))
    g.audit_before = dict(current) if current else {}
    result, status = care.transition(aid, 'process', {'actor_name': g.account['name']})
    return jsonify(result), status


@app.route("/api/alerts/<int:aid>/close", methods=["POST"])
def api_alert_close(aid):
    current = db.query_one('SELECT status,assignee,assignee_role FROM alerts WHERE id=?', (aid,))
    g.audit_before = dict(current) if current else {}
    data = request.get_json(silent=True) or {}
    data['actor_name'] = g.account['name']
    result, status = care.transition(aid, 'close', data)
    return jsonify(result), status


@app.route("/api/simulator/trigger", methods=["POST"])
def api_simulator():
    try:
        data = request.get_json(silent=True) or {}
        elder_id = data.get('elder_id')
        if elder_id is None:
            where, args = access.scope_sql(g.account, 'e')
            first = db.query_one(f"SELECT e.id FROM elders e WHERE {where} AND e.status!='archived' ORDER BY e.id LIMIT 1", args)
            elder_id = first['id'] if first else None
        if not elder_id:
            return jsonify(ok=False, message='当前范围内没有可用老人档案'), 404
        if not access.elder_accessible(g.account, elder_id):
            return jsonify(ok=False, message='老人不在数据范围内'), 404
        return jsonify(care.assess(data, elder_id))
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400


@app.route('/api/care/notices/<int:nid>/read', methods=['POST'])
def read_care_notice(nid):
    notice = db.query_one("SELECT n.id,a.elder_id FROM care_notices n JOIN alerts a ON a.id=n.alert_id WHERE n.id=? AND n.role='family'", (nid,))
    if not notice:
        return jsonify(ok=False, message='消息不存在'), 404
    if not access.elder_accessible(g.account, notice['elder_id']):
        return jsonify(ok=False, message='无权查看此消息'), 403
    db.execute('UPDATE care_notices SET read_at=COALESCE(read_at,?) WHERE id=?', (care.stamp(), nid))
    return jsonify(ok=True)


@app.route('/api/care/alerts/<int:aid>/demo-timeout', methods=['POST'])
def demo_timeout(aid):
    if not access.alert_accessible(g.account, aid):
        return jsonify(ok=False, message='工单不存在或不在数据范围内'), 404
    row = db.query_one("SELECT a.status,c.alert_id FROM alerts a JOIN care_cases c ON c.alert_id=a.id WHERE a.id=?", (aid,))
    if not row or row['status'] == 'closed':
        return jsonify(ok=False, message='仅支持未归档的新流程工单'), 400
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('UPDATE care_cases SET due_at=? WHERE alert_id=?', (care.stamp(), aid))
        care.log(conn, aid, '演示控制台', '模拟期限到达', '仅将此工单当前响应期限设为现在，验证超时提醒。')
        conn.commit()
    finally:
        conn.close()
    care.scan_due()
    return jsonify(ok=True)


# ---------------------------------------------------------------- React SPA
@app.route("/")
@app.route("/elder/home")
@app.route("/elder/sos")
@app.route("/family/overview")
@app.route("/community/dashboard")
@app.route("/community/elders")
@app.route("/community/alerts")
@app.route("/volunteer/tasks")
@app.route("/demo/simulator")
def react_app():
    return send_from_directory(REACT_DIST, "index.html")


@app.route("/<path:path>")
def react_fallback(path):
    if path.startswith("api/"):
        return jsonify({"ok": False, "message": "接口不存在"}), 404
    return send_from_directory(REACT_DIST, "index.html")


# ---------------------------------------------------------------- 启动
if __name__ == "__main__":
    db.init_db()
    care.start_monitor()
    start_backup_monitor()
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
