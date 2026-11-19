# -*- coding: utf-8 -*-
"""
安芯 · 独居老人 AI 安全守护与社区关爱平台  (第一版 Demo)
=========================================================
运行方式（PyCharm）：
  1. pip install -r requirements.txt
  2. 右键运行本文件（或终端执行 python app.py）
  3. 浏览器打开 http://127.0.0.1:5000

技术栈：React + Flask + Jinja2 + SQLite + 原生 JS + ECharts(CDN)
页面清单见 README.md
"""
import os
import json
import re
import sqlite3
from functools import wraps
from datetime import datetime, timedelta

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

import db
import anomaly

app = Flask(__name__)
app.secret_key = os.environ.get("ANXIN_SECRET_KEY", "anxin-demo-secret-key")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

DEMO_ELDER_ID = 1  # 演示主角：张桂芳（82 岁独居，儿子李伟在上海）

LEVEL_TEXT = {"green": "平安", "yellow": "需关注", "red": "紧急"}
STATUS_TEXT = {
    "pending": "待核实",
    "dispatched": "已派单",
    "processing": "处置中",
    "follow_up": "待回访",
    "closed": "已归档",
}
ROLE_TEXT = {"elder": "老人", "family": "子女", "community": "社区", "volunteer": "志愿者"}
ROLE_HOME = {
    "elder": "/elder/home",
    "family": "/family/overview",
    "community": "/community/dashboard",
    "volunteer": "/volunteer/tasks",
}
ACCOUNT_HOME = {"admin": "/"}
REACT_DIST = os.path.join(app.static_folder, "react")


def require_roles(*roles, allow_preview=False):
    """Authorize regular accounts by role while granting administrators full access."""
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            role = session.get("role")
            account_type = None
            account_id = session.get("auth_user_id")
            if account_id:
                account = db.query_one("SELECT account_type, role FROM users WHERE id=?", (account_id,))
                if not account:
                    session.clear()
                    return jsonify({"ok": False, "message": "登录已失效，请重新登录"}), 401
                role = account["role"]
                account_type = account["account_type"]
            if not role:
                return jsonify({"ok": False, "message": "请先选择演示角色"}), 401
            if account_type == "admin":
                return view(*args, **kwargs)
            preview = (
                allow_preview
                and request.args.get("preview") == "1"
                and role in ROLE_HOME
                and account_id is None
            )
            if role not in roles and not preview:
                return jsonify({"ok": False, "message": "当前角色无权执行此操作"}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorate


def record_transition(alert_id, old_status, new_status, note=""):
    db.execute(
        """INSERT INTO work_order_logs
           (alert_id, from_status, to_status, actor_role, note, created_at)
           VALUES (?,?,?,?,?,?)""",
        (alert_id, old_status, new_status, session.get("role", "system"), note, now_str()),
    )


def get_alert(alert_id):
    return db.query_one("SELECT * FROM alerts WHERE id=?", (alert_id,))


def public_account(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "phone": row["phone"],
        "account_type": row["account_type"],
        "role": row["role"],
    }


def establish_account_session(row):
    session.clear()
    session["auth_user_id"] = row["id"]
    session["role"] = row["role"]
    session["account_type"] = row["account_type"]
    session["username"] = row["username"]


def normalize_phone(value):
    value = re.sub(r"[\s()-]", "", value or "")
    if value.startswith("00"):
        value = "+" + value[2:]
    return value


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


# ---------------------------------------------------------------- 会话与 React 页面入口
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account_id = session.get("auth_user_id")
        if account_id:
            account = db.query_one("SELECT account_type, role FROM users WHERE id=?", (account_id,))
            if account:
                return redirect(ACCOUNT_HOME[account["account_type"]])
            session.clear()
        role = request.form.get("role", "family")
        if role not in ROLE_HOME:
            role = "family"
        session["role"] = role
        return redirect(ROLE_HOME[role])
    return send_from_directory(REACT_DIST, "index.html")


@app.route("/api/session", methods=["GET", "POST", "DELETE"])
def api_session():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        role = data.get("role", "")
        if role not in ROLE_HOME:
            return jsonify({"ok": False, "message": "无效的登录角色"}), 400
        account_id = session.get("auth_user_id")
        if account_id:
            account = db.query_one("SELECT account_type, role FROM users WHERE id=?", (account_id,))
            if not account:
                session.clear()
                return jsonify({"ok": False, "message": "登录已失效，请重新登录"}), 401
            if account["account_type"] != "admin" and role != account["role"]:
                return jsonify({"ok": False, "message": "账号不能切换为其他角色"}), 403
        session["role"] = role
    elif request.method == "DELETE":
        session.clear()

    role = session.get("role")
    account = None
    if session.get("auth_user_id"):
        row = db.query_one("SELECT * FROM users WHERE id=?", (session["auth_user_id"],))
        if row:
            account = public_account(row)
            role = session.get("role") if row["account_type"] == "admin" else row["role"]
            if role not in ROLE_HOME:
                role = row["role"]
        else:
            session.clear()
            role = None
    return jsonify({
        "ok": True,
        "role": role,
        "role_name": ROLE_TEXT.get(role, ""),
        "home": ACCOUNT_HOME.get(account["account_type"], ROLE_HOME.get(role, "/login")) if account else ROLE_HOME.get(role, "/login"),
        "authenticated": account is not None,
        "account": account,
        "today": today_str(),
        "weekday": WEEKDAYS[datetime.now().weekday()],
    })


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    account_type = data.get("account_type", "")
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""
    selected_role = data.get("role")
    valid_account_type = account_type == "admin" or account_type == "user" and selected_role in ROLE_HOME
    if not valid_account_type or not identifier or not password:
        return jsonify({"ok": False, "message": "请选择身份并填写账号和密码"}), 400

    phone = normalize_phone(identifier)
    account = db.query_one(
        """SELECT * FROM users WHERE account_type=? AND
           (username=? COLLATE NOCASE OR email=? COLLATE NOCASE OR phone=?) LIMIT 1""",
        (account_type, identifier, identifier.lower(), phone),
    )
    if not account:
        return jsonify({
            "ok": False,
            "code": "USER_NOT_FOUND",
            "message": "没有找到匹配的账号，可以切换到注册。",
        }), 404
    if not check_password_hash(account["password_hash"], password):
        return jsonify({"ok": False, "message": "账号或密码不正确"}), 401
    if account_type == "user" and account["role"] != selected_role:
        return jsonify({"ok": False, "message": "该账号不属于所选用户角色，请重新选择"}), 403

    establish_account_session(account)
    return jsonify({
        "ok": True,
        "authenticated": True,
        "role": account["role"],
        "home": ACCOUNT_HOME[account["account_type"]] if account["account_type"] == "admin" else ROLE_HOME[account["role"]],
        "account": public_account(account),
    })


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower() or None
    phone = normalize_phone((data.get("phone") or "").strip()) or None
    role = data.get("role")
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""

    if len(username) < 2 or len(username) > 32 or any(char.isspace() for char in username):
        return jsonify({"ok": False, "message": "用户名需为 2 至 32 个字符且不能包含空格"}), 400
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"ok": False, "message": "邮箱格式不正确"}), 400
    if phone and not re.fullmatch(r"\+?\d{7,20}", phone):
        return jsonify({"ok": False, "message": "电话格式不正确"}), 400
    if not email and not phone:
        return jsonify({"ok": False, "message": "邮箱和电话至少填写一项"}), 400
    if role not in ROLE_HOME:
        return jsonify({"ok": False, "message": "请选择普通用户角色"}), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify({"ok": False, "message": "密码长度需为 8 至 128 位"}), 400
    if password != password_confirm:
        return jsonify({"ok": False, "message": "两次输入的密码不一致"}), 400

    duplicate = db.query_one(
        """SELECT id FROM users WHERE username=? COLLATE NOCASE
           OR (? IS NOT NULL AND email=? COLLATE NOCASE)
           OR (? IS NOT NULL AND phone=?) LIMIT 1""",
        (username, email, email, phone, phone),
    )
    if duplicate:
        return jsonify({"ok": False, "message": "用户名、邮箱或电话已被使用"}), 409

    try:
        account_id = db.execute(
            """INSERT INTO users
               (username, email, phone, password_hash, account_type, role, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                username,
                email,
                phone,
                generate_password_hash(password),
                "user",
                role,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "message": "用户名、邮箱或电话已被使用"}), 409

    account = db.query_one("SELECT * FROM users WHERE id=?", (account_id,))
    establish_account_session(account)
    return jsonify({
        "ok": True,
        "authenticated": True,
        "role": account["role"],
        "home": ROLE_HOME[role],
        "account": public_account(account),
    }), 201


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.clear()
    return jsonify({"ok": True, "authenticated": False})


@app.route("/api/elder/home")
@require_roles("elder", allow_preview=True)
def api_elder_home():
    elder = dict(db.query_one("SELECT * FROM elders WHERE id=?", (DEMO_ELDER_ID,)))
    checked_today = bool(elder["last_checkin"] and elder["last_checkin"].startswith(today_str()))
    return jsonify({
        "elder": elder,
        "checked_today": checked_today,
        "today": today_str(),
        "weekday": WEEKDAYS[datetime.now().weekday()],
    })


@app.route("/api/family/overview")
@require_roles("family", allow_preview=True)
def api_family_overview():
    elder = dict(db.query_one("SELECT * FROM elders WHERE id=?", (DEMO_ELDER_ID,)))
    events = db.query("SELECT * FROM events WHERE elder_id=? AND ts LIKE ? ORDER BY ts",
                      (DEMO_ELDER_ID, today_str() + "%"))
    if elder["last_checkin"] and elder["last_checkin"].startswith(today_str()):
        events = [event for event in events if "报平安" not in event["text"]]
    readings = db.query("SELECT * FROM readings WHERE elder_id=? ORDER BY day", (DEMO_ELDER_ID,))
    alerts = db.query("SELECT * FROM alerts WHERE elder_id=? ORDER BY created_at DESC LIMIT 6", (DEMO_ELDER_ID,))
    return jsonify({
        "elder": elder,
        "events": [dict(event) for event in events],
        "readings": [dict(reading) for reading in readings],
        "alerts": [dict(alert) for alert in alerts],
    })


@app.route("/api/elders")
@require_roles("community", allow_preview=True)
def api_elders():
    level = request.args.get("level", "")
    if level in ("green", "yellow", "red"):
        elders = db.query("SELECT * FROM elders WHERE risk_level=? ORDER BY age DESC", (level,))
    else:
        elders = db.query("""SELECT * FROM elders ORDER BY
                           CASE risk_level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
                           age DESC""")
    needs = db.query("""SELECT n.*, e.name AS elder_name FROM needs n
                        LEFT JOIN elders e ON e.id = n.elder_id ORDER BY n.id""")
    services = db.query("""SELECT * FROM service_resources WHERE active=1
                           ORDER BY category, name""")
    baseline_row = db.query_one("SELECT * FROM behavior_baselines WHERE elder_id=?", (DEMO_ELDER_ID,))
    latest_reading = db.query_one(
        "SELECT * FROM sensor_readings WHERE elder_id=? ORDER BY observed_at DESC LIMIT 1",
        (DEMO_ELDER_ID,),
    )
    baseline = dict(baseline_row) if baseline_row else None
    if baseline:
        baseline["feature_summary"] = json.loads(baseline["feature_summary"] or "{}")
    return jsonify({
        "elders": [dict(elder) for elder in elders],
        "needs": [dict(need) for need in needs],
        "services": [dict(service) for service in services],
        "baseline": baseline,
        "latest_reading": dict(latest_reading) if latest_reading else None,
        "current_level": level,
    })


@app.route("/api/volunteer/tasks")
@require_roles("volunteer", allow_preview=True)
def api_volunteer_tasks():
    tasks = db.query("""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                        LEFT JOIN elders e ON e.id = a.elder_id
                        WHERE a.assignee_role = 'volunteer' AND a.status IN ('dispatched','processing')
                        ORDER BY a.level = 'red' DESC, a.created_at""")
    done = db.query("""SELECT a.*, e.name AS elder_name FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       WHERE a.assignee_role = 'volunteer' AND a.status = 'closed'
                       ORDER BY a.closed_at DESC LIMIT 5""")
    return jsonify({
        "tasks": [dict(task) for task in tasks],
        "done": [dict(task) for task in done],
    })


# ---------------------------------------------------------------- API
@app.route("/api/checkin", methods=["POST"])
@require_roles("elder")
def api_checkin():
    """老人打卡"""
    ts = now_str()
    db.execute("UPDATE elders SET last_checkin=?, risk_level='green' WHERE id=?", (ts, DEMO_ELDER_ID))
    db.execute("INSERT INTO events (elder_id, ts, icon, text, kind) VALUES (?,?,?,?,?)",
               (DEMO_ELDER_ID, ts, "✅", "在「今日平安」报平安", "normal"))
    db.execute("UPDATE readings SET checkin=1 WHERE elder_id=? AND day=?", (DEMO_ELDER_ID, today_str()))
    return jsonify({"ok": True, "time": ts[-5:]})


@app.route("/api/sos", methods=["POST"])
@require_roles("elder")
def api_sos():
    """触发 SOS：生成红色预警并通知家属与社区"""
    ts = now_str()
    n = db.query_one("SELECT COUNT(*) AS n FROM alerts")["n"]
    code = "AL-" + datetime.now().strftime("%Y%m%d") + "-%04d" % (1000 + n + 1)
    db.execute("""INSERT INTO alerts (code, elder_id, level, trigger_type, reason, created_at, status)
                  VALUES (?,?,?,?,?,?, 'pending')""",
               (code, DEMO_ELDER_ID, "red", "sos", "老人触发 SOS 一键呼救（" + ts + "）", ts))
    db.execute("UPDATE elders SET risk_level='red' WHERE id=?", (DEMO_ELDER_ID,))
    return jsonify({"ok": True, "notified": ["儿子 李伟 ✔", "社区值班 王芳 ✔", "志愿者 赵敏（就近 320m）✔"]})


@app.route("/api/dashboard")
@require_roles("community", allow_preview=True)
def api_dashboard():
    """驾驶舱数据（前端每 5 秒轮询）"""
    elders = db.query("SELECT id, name, age, x, y, risk_level FROM elders")
    cnt = {"green": 0, "yellow": 0, "red": 0}
    for e in elders:
        cnt[e["risk_level"]] = cnt.get(e["risk_level"], 0) + 1

    status_counts = {k: 0 for k in STATUS_TEXT}
    for a in db.query("SELECT status, COUNT(*) AS n FROM alerts GROUP BY status"):
        status_counts[a["status"]] = a["n"]

    recent = db.query("""SELECT a.*, e.name AS elder_name, e.age FROM alerts a
                         LEFT JOIN elders e ON e.id = a.elder_id
                         ORDER BY a.created_at DESC LIMIT 8""")

    # 近 24 小时预警趋势（4 小时一桶）
    trend = []
    now = datetime.now()
    for i in range(6, 0, -1):
        start = now - timedelta(hours=i * 4)
        end = now - timedelta(hours=(i - 1) * 4)
        row = db.query_one("SELECT COUNT(*) AS n FROM alerts WHERE created_at BETWEEN ? AND ?",
                           (start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M")))
        trend.append(row["n"])

    devices_total = sum(1 for _ in elders) * 4
    devices_online = devices_total - 1
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
@require_roles("community", allow_preview=True)
def api_alerts():
    """全部预警工单（预警工单页轮询）"""
    rows = db.query("""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       ORDER BY CASE a.level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
                                CASE a.status WHEN 'pending' THEN 0 WHEN 'dispatched' THEN 1
                                     WHEN 'processing' THEN 2 ELSE 3 END, a.created_at DESC""")
    return jsonify({"alerts": [dict(r) for r in rows]})


@app.route("/api/alerts/<int:aid>/dispatch", methods=["POST"])
@require_roles("community")
def api_alert_dispatch(aid):
    data = request.get_json(silent=True) or {}
    assignee = data.get("assignee", "王芳").strip()
    if not assignee:
        return jsonify({"ok": False, "message": "请指定负责人"}), 400
    alert = get_alert(aid)
    if not alert:
        return jsonify({"ok": False, "message": "工单不存在"}), 404
    if alert["status"] != "pending":
        return jsonify({"ok": False, "message": "仅待核实工单可派单"}), 409
    arole = {"王芳": "worker", "赵敏": "volunteer", "物业老周": "property"}.get(assignee, "worker")
    db.execute("UPDATE alerts SET status='dispatched', assignee=?, assignee_role=? WHERE id=?",
               (assignee, arole, aid))
    record_transition(aid, "pending", "dispatched", f"派单给{assignee}")
    return jsonify({"ok": True})


@app.route("/api/alerts/<int:aid>/process", methods=["POST"])
@require_roles("volunteer", "community")
def api_alert_process(aid):
    alert = get_alert(aid)
    if not alert:
        return jsonify({"ok": False, "message": "工单不存在"}), 404
    if alert["status"] != "dispatched":
        return jsonify({"ok": False, "message": "仅已派单工单可开始处置"}), 409
    if session.get("role") == "volunteer" and (alert["assignee_role"] != "volunteer" or alert["assignee"] != "赵敏"):
        return jsonify({"ok": False, "message": "该工单未派给志愿者"}), 403
    db.execute("UPDATE alerts SET status='processing' WHERE id=?", (aid,))
    record_transition(aid, "dispatched", "processing", "服务人员已到场")
    return jsonify({"ok": True})


@app.route("/api/alerts/<int:aid>/close", methods=["POST"])
@require_roles("volunteer", "community")
def api_alert_close(aid):
    data = request.get_json(silent=True) or {}
    result = (data.get("result") or "").strip()
    alert = get_alert(aid)
    if not alert:
        return jsonify({"ok": False, "message": "工单不存在"}), 404
    if alert["status"] != "processing":
        return jsonify({"ok": False, "message": "仅处置中的工单可提交回执"}), 409
    if session.get("role") == "volunteer" and (alert["assignee_role"] != "volunteer" or alert["assignee"] != "赵敏"):
        return jsonify({"ok": False, "message": "该工单未派给志愿者"}), 403
    if not result:
        return jsonify({"ok": False, "message": "请填写处置结果"}), 400
    db.execute("UPDATE alerts SET status='follow_up', result=? WHERE id=?", (result, aid))
    record_transition(aid, "processing", "follow_up", "处置回执已提交")
    return jsonify({"ok": True, "status": "follow_up"})


@app.route("/api/alerts/<int:aid>/follow-up", methods=["POST"])
@require_roles("community", "family")
def api_alert_follow_up(aid):
    data = request.get_json(silent=True) or {}
    result = (data.get("result") or "").strip()
    satisfaction = data.get("satisfaction")
    alert = get_alert(aid)
    if not alert:
        return jsonify({"ok": False, "message": "工单不存在"}), 404
    if alert["status"] != "follow_up":
        return jsonify({"ok": False, "message": "工单当前不在待回访状态"}), 409
    if session.get("role") == "family" and alert["elder_id"] != DEMO_ELDER_ID:
        return jsonify({"ok": False, "message": "只能回访关联老人"}), 403
    if not result:
        return jsonify({"ok": False, "message": "请填写回访结果"}), 400
    if satisfaction is not None and (not isinstance(satisfaction, int) or not 1 <= satisfaction <= 5):
        return jsonify({"ok": False, "message": "满意度需为 1 至 5"}), 400
    ts = now_str()
    db.execute(
        "INSERT INTO follow_up_records (alert_id, actor_role, result, satisfaction, created_at) VALUES (?,?,?,?,?)",
        (aid, session["role"], result, satisfaction, ts),
    )
    db.execute("UPDATE alerts SET status='closed', closed_at=?, result=? WHERE id=?", (ts, result, aid))
    record_transition(aid, "follow_up", "closed", "回访完成" + (f"，满意度{satisfaction}/5" if satisfaction else ""))
    # 该老人若无其他未归档工单，风险回落为绿色（误报学习：简化版）
    open_cnt = db.query_one("SELECT COUNT(*) AS n FROM alerts WHERE elder_id=(SELECT elder_id FROM alerts WHERE id=?) AND status != 'closed'", (aid,))["n"]
    if open_cnt == 0:
        db.execute("""UPDATE elders SET risk_level='green' WHERE id=
                      (SELECT elder_id FROM alerts WHERE id=?)""", (aid,))
    return jsonify({"ok": True})


@app.route("/api/simulator/trigger", methods=["POST"])
@require_roles("community")
def api_simulator():
    """IoT 数据模拟器：注入异常场景，秒级生成预警（答辩演示总开关）"""
    data = request.get_json(force=True)
    scenario = data.get("scenario", "")
    ts = now_str()
    n = db.query_one("SELECT COUNT(*) AS n FROM alerts")["n"]

    scenarios = {
        "fall": {
            "door_events": 1, "water_liters": 0, "activity_minutes": 0,
            "room_transitions": 0, "night_activity": 0, "fall_confidence": 0.98,
            "still_minutes": 18, "trigger_type": "fall", "source": "visual_demo",
        },
        "no_water": {
            "door_events": 1, "water_liters": 0, "activity_minutes": 145,
            "room_transitions": 2, "night_activity": 0, "fall_confidence": 0,
            "still_minutes": 0, "trigger_type": "behavior_anomaly", "source": "synthetic_iot",
        },
        "door_stuck": {
            "door_events": 0, "water_liters": 18, "activity_minutes": 40,
            "room_transitions": 1, "night_activity": 0, "fall_confidence": 0,
            "still_minutes": 0, "trigger_type": "behavior_anomaly", "source": "synthetic_iot",
        },
    }
    if scenario not in scenarios:
        return jsonify({"ok": False, "msg": "未知场景：" + scenario}), 400

    reading = scenarios[scenario]
    elder_id = DEMO_ELDER_ID
    observed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """INSERT INTO sensor_readings
           (elder_id, observed_at, door_events, water_liters, activity_minutes,
            room_transitions, night_activity, fall_confidence, still_minutes, source)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (elder_id, observed_at, reading["door_events"], reading["water_liters"],
         reading["activity_minutes"], reading["room_transitions"], reading["night_activity"],
         reading["fall_confidence"], reading["still_minutes"], reading["source"]),
    )
    evaluation = anomaly.evaluate(elder_id, reading)
    level = evaluation["level"]
    ttype = reading["trigger_type"]
    reason = evaluation["reason"]
    code = "AL-" + datetime.now().strftime("%Y%m%d") + "-%04d" % (1000 + n + 1)
    alert_id = db.execute(
        """INSERT INTO alerts
           (code, elder_id, level, trigger_type, reason, created_at, status,
            anomaly_percentile, baseline_scope)
           VALUES (?,?,?,?,?,?, 'pending',?,?)""",
        (code, elder_id, level, ttype, reason, ts,
         evaluation["anomaly_percentile"], evaluation["baseline_scope"]),
    )
    record_transition(alert_id, None, "pending", "时序窗口异常检测生成预警")
    if level in ("yellow", "red"):
        category = "visit"
        descr = f"异常事件 {code} 触发探访核实：{reason}"
        need_id = db.execute(
            """INSERT INTO needs (elder_id, category, descr, urgency, status, provider, source_alert_id)
               VALUES (?,?,?,?,?,?,?)""",
            (elder_id, category, descr, "high" if level == "red" else "normal", "待对接", None, alert_id),
        )
        resource = db.query_one(
            "SELECT * FROM service_resources WHERE category=? AND active=1 AND available>0 ORDER BY available DESC LIMIT 1",
            (category,),
        )
        if resource:
            db.execute(
                "INSERT OR IGNORE INTO need_service_links (need_id, resource_id, status, linked_at) VALUES (?,?,?,?)",
                (need_id, resource["id"], "matched", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            db.execute(
                "UPDATE needs SET status='已转服务', provider=? WHERE id=?",
                (resource["provider"], need_id),
            )
            db.execute(
                "UPDATE service_resources SET available=MAX(0, available-1) WHERE id=?",
                (resource["id"],),
            )
    db.execute("UPDATE elders SET risk_level=? WHERE id=?", (level, elder_id))
    elder = db.query_one("SELECT name FROM elders WHERE id=?", (elder_id,))
    return jsonify({
        "ok": True,
        "alert_id": alert_id,
        "level": level,
        "anomaly_percentile": evaluation["anomaly_percentile"],
        "baseline_scope": evaluation["baseline_scope"],
        "sample_count": evaluation["sample_count"],
        "msg": f"已写入时序数据并按 {evaluation['baseline_scope']} 基线评分。{elder['name']} 生成{LEVEL_TEXT[level]}预警：{reason}",
    })


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
    app.run(host="127.0.0.1", port=5000, debug=True)
