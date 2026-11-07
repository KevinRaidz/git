# -*- coding: utf-8 -*-
"""
安芯 · 独居老人 AI 安全守护与社区关爱平台  (第一版 Demo)
=========================================================
运行方式（PyCharm）：
  1. pip install -r requirements.txt
  2. 右键运行本文件（或终端执行 python app.py）
  3. 浏览器打开 http://127.0.0.1:5000

技术栈：Flask + Jinja2 + SQLite + 原生 JS + ECharts(CDN)
页面清单见 README.md
"""
from datetime import datetime, timedelta
from flask import Flask, render_template, request, session, jsonify, redirect, url_for

import db

app = Flask(__name__)
app.secret_key = "anxin-demo-secret-key"  # 生产环境请换成随机密钥

DEMO_ELDER_ID = 1  # 演示主角：张桂芳（82 岁独居，儿子李伟在上海）

LEVEL_TEXT = {"green": "平安", "yellow": "需关注", "red": "紧急"}
STATUS_TEXT = {"pending": "待核实", "dispatched": "已派单", "processing": "处置中", "closed": "已归档"}


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


# ---------------------------------------------------------------- 全局模板变量
@app.context_processor
def inject_globals():
    return {
        "role": session.get("role"),
        "role_name": {"elder": "老人", "family": "子女", "community": "社区", "volunteer": "志愿者"}.get(session.get("role"), ""),
        "level_text": LEVEL_TEXT,
        "status_text": STATUS_TEXT,
        "today": today_str(),
        "weekday": WEEKDAYS[datetime.now().weekday()],
    }


# ---------------------------------------------------------------- 页面路由
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session["role"] = request.form.get("role", "family")
        return redirect({
            "elder": url_for("elder_home"),
            "family": url_for("family_overview"),
            "community": url_for("community_dashboard"),
            "volunteer": url_for("volunteer_tasks"),
        }[session["role"]])
    return render_template("login.html")


# ============================== 老人端 ==============================
@app.route("/elder/home")
def elder_home():
    elder = db.query_one("SELECT * FROM elders WHERE id=?", (DEMO_ELDER_ID,))
    checked_today = elder["last_checkin"] and elder["last_checkin"].startswith(today_str())
    return render_template("elder_home.html", elder=elder, checked_today=checked_today)


@app.route("/elder/sos")
def elder_sos():
    elder = db.query_one("SELECT * FROM elders WHERE id=?", (DEMO_ELDER_ID,))
    return render_template("elder_sos.html", elder=elder)


# ============================== 子女端 ==============================
@app.route("/family/overview")
def family_overview():
    elder = db.query_one("SELECT * FROM elders WHERE id=?", (DEMO_ELDER_ID,))
    events = db.query("SELECT * FROM events WHERE elder_id=? AND ts LIKE ? ORDER BY ts",
                      (DEMO_ELDER_ID, today_str() + "%"))
    # 打卡事件插入时间轴
    if elder["last_checkin"] and elder["last_checkin"].startswith(today_str()):
        events = [e for e in events if "报平安" not in e["text"]]
    readings = db.query("SELECT * FROM readings WHERE elder_id=? ORDER BY day", (DEMO_ELDER_ID,))
    alerts = db.query("SELECT * FROM alerts WHERE elder_id=? ORDER BY created_at DESC LIMIT 6", (DEMO_ELDER_ID,))
    return render_template("family_overview.html", elder=elder, events=events,
                           readings=readings, alerts=alerts)


# ============================== 社区端 ==============================
@app.route("/community/dashboard")
def community_dashboard():
    return render_template("dashboard.html")


@app.route("/community/elders")
def community_elders():
    level = request.args.get("level", "")
    if level in ("green", "yellow", "red"):
        elders = db.query("SELECT * FROM elders WHERE risk_level=? ORDER BY risk_level DESC, age DESC", (level,))
    else:
        elders = db.query("SELECT * FROM elders ORDER BY CASE risk_level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END, age DESC")
    needs = db.query("""SELECT n.*, e.name AS elder_name FROM needs n
                        LEFT JOIN elders e ON e.id = n.elder_id ORDER BY n.id""")
    return render_template("elders.html", elders=elders, needs=needs, current_level=level)


@app.route("/community/alerts")
def community_alerts():
    return render_template("alerts.html")


# ============================== 志愿者端 ==============================
@app.route("/volunteer/tasks")
def volunteer_tasks():
    tasks = db.query("""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                        LEFT JOIN elders e ON e.id = a.elder_id
                        WHERE a.assignee_role = 'volunteer' AND a.status IN ('dispatched','processing')
                        ORDER BY a.level = 'red' DESC, a.created_at""")
    done = db.query("""SELECT a.*, e.name AS elder_name FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       WHERE a.assignee_role = 'volunteer' AND a.status = 'closed'
                       ORDER BY a.closed_at DESC LIMIT 5""")
    return render_template("volunteer.html", tasks=tasks, done=done)


# ============================== 演示模拟器 ==============================
@app.route("/demo/simulator")
def simulator():
    return render_template("simulator.html")


# ---------------------------------------------------------------- API
@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    """老人打卡"""
    ts = now_str()
    db.execute("UPDATE elders SET last_checkin=?, risk_level='green' WHERE id=?", (ts, DEMO_ELDER_ID))
    db.execute("INSERT INTO events (elder_id, ts, icon, text, kind) VALUES (?,?,?,?,?)",
               (DEMO_ELDER_ID, ts, "✅", "在「今日平安」报平安", "normal"))
    db.execute("UPDATE readings SET checkin=1 WHERE elder_id=? AND day=?", (DEMO_ELDER_ID, today_str()))
    return jsonify({"ok": True, "time": ts[-5:]})


@app.route("/api/sos", methods=["POST"])
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
def api_alerts():
    """全部预警工单（预警工单页轮询）"""
    rows = db.query("""SELECT a.*, e.name AS elder_name, e.age, e.address FROM alerts a
                       LEFT JOIN elders e ON e.id = a.elder_id
                       ORDER BY CASE a.level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END,
                                CASE a.status WHEN 'pending' THEN 0 WHEN 'dispatched' THEN 1
                                     WHEN 'processing' THEN 2 ELSE 3 END, a.created_at DESC""")
    return jsonify({"alerts": [dict(r) for r in rows]})


@app.route("/api/alerts/<int:aid>/dispatch", methods=["POST"])
def api_alert_dispatch(aid):
    data = request.get_json(force=True)
    assignee = data.get("assignee", "王芳")
    arole = {"王芳": "worker", "赵敏": "volunteer", "物业老周": "property"}.get(assignee, "worker")
    db.execute("UPDATE alerts SET status='dispatched', assignee=?, assignee_role=? WHERE id=?",
               (assignee, arole, aid))
    return jsonify({"ok": True})


@app.route("/api/alerts/<int:aid>/process", methods=["POST"])
def api_alert_process(aid):
    db.execute("UPDATE alerts SET status='processing' WHERE id=?", (aid,))
    return jsonify({"ok": True})


@app.route("/api/alerts/<int:aid>/close", methods=["POST"])
def api_alert_close(aid):
    data = request.get_json(force=True)
    result = data.get("result", "已上门核实，一切安好")
    db.execute("UPDATE alerts SET status='closed', closed_at=?, result=? WHERE id=?",
               (now_str(), result, aid))
    # 该老人若无其他未归档工单，风险回落为绿色（误报学习：简化版）
    open_cnt = db.query_one("SELECT COUNT(*) AS n FROM alerts WHERE elder_id=(SELECT elder_id FROM alerts WHERE id=?) AND status != 'closed'", (aid,))["n"]
    if open_cnt == 0:
        db.execute("""UPDATE elders SET risk_level='green' WHERE id=
                      (SELECT elder_id FROM alerts WHERE id=?)""", (aid,))
    return jsonify({"ok": True})


@app.route("/api/simulator/trigger", methods=["POST"])
def api_simulator():
    """IoT 数据模拟器：注入异常场景，秒级生成预警（答辩演示总开关）"""
    data = request.get_json(force=True)
    scenario = data.get("scenario", "")
    ts = now_str()
    n = db.query_one("SELECT COUNT(*) AS n FROM alerts")["n"]

    scenarios = {
        # 场景：夜间跌倒（红色）
        "fall": (DEMO_ELDER_ID, "red", "low_activity",
                 "红外监测：卧室监测到跌倒姿态，已 15 分钟未起身"),
        # 场景：全天无用水（黄色）
        "no_water": (DEMO_ELDER_ID, "yellow", "no_checkin",
                     "今日用水 0L，较近 14 天均值下降 100%，门磁今日仅开合 1 次"),
        # 场景：门磁长时间未动（黄色）
        "door_stuck": (DEMO_ELDER_ID, "yellow", "device_offline",
                       "门磁已 36 小时未开合，红外夜间无活动记录"),
    }
    if scenario not in scenarios:
        return jsonify({"ok": False, "msg": "未知场景：" + scenario}), 400

    elder_id, level, ttype, reason = scenarios[scenario]
    code = "AL-" + datetime.now().strftime("%Y%m%d") + "-%04d" % (1000 + n + 1)
    db.execute("""INSERT INTO alerts (code, elder_id, level, trigger_type, reason, created_at, status)
                  VALUES (?,?,?,?,?,?, 'pending')""", (code, elder_id, level, ttype, reason + "（模拟数据 " + ts + "）", ts))
    db.execute("UPDATE elders SET risk_level=? WHERE id=?", (level, elder_id))
    elder = db.query_one("SELECT name FROM elders WHERE id=?", (elder_id,))
    return jsonify({"ok": True, "msg": "已注入场景，%s 已生成 %s 预警：%s" % (elder["name"], LEVEL_TEXT[level], reason)})


# ---------------------------------------------------------------- 启动
if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
