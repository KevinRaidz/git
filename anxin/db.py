# -*- coding: utf-8 -*-
"""
安芯 · 数据库层
SQLite 建表 + 演示数据种子。首次运行 app.py 时自动初始化 anxin.db。
改表结构后删除 anxin.db 重新运行即可重新生成演示数据。
"""
import os
import sqlite3
import random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "anxin.db")

random.seed(42)  # 保证每次生成的演示数据一致

# 演示社区的老人名单（id=1 张桂芳为演示主角）
ELDERS_SEED = [
    # (姓名, 年龄, 性别, 住址, 独居, 慢病)
    ("张桂芳", 82, "女", "幸福里 3栋2单元401", 1, "高血压、糖尿病"),
    ("李建国", 79, "男", "幸福里 3栋1单元502", 1, "冠心病"),
    ("王秀英", 76, "女", "幸福里 5栋2单元302", 0, "关节炎"),
    ("刘德海", 85, "男", "幸福里 2栋1单元101", 1, "高血压"),
    ("陈淑珍", 88, "女", "幸福里 6栋3单元601", 1, "骨质疏松、高血压"),
    ("杨振邦", 74, "男", "幸福里 4栋2单元203", 0, "无"),
    ("赵兰英", 81, "女", "幸福里 1栋3单元404", 1, "糖尿病"),
    ("孙福贵", 90, "男", "幸福里 6栋1单元102", 1, "慢阻肺"),
    ("周玉梅", 77, "女", "幸福里 2栋2单元501", 0, "无"),
    ("吴长顺", 83, "男", "幸福里 5栋1单元304", 1, "前列腺疾病"),
    ("郑桂兰", 72, "女", "幸福里 4栋3单元202", 0, "高血压"),
    ("王铁柱", 86, "男", "幸福里 1栋2单元303", 1, "脑梗后遗症"),
    ("冯巧云", 78, "女", "幸福里 3栋3单元105", 1, "糖尿病"),
    ("蒋友三", 75, "男", "幸福里 5栋3单元602", 0, "无"),
    ("沈明兰", 84, "女", "幸福里 6栋2单元403", 1, "阿尔茨海默病（早期）"),
    ("韩广田", 80, "男", "幸福里 2栋3单元204", 1, "高血压"),
    ("曹凤霞", 73, "女", "幸福里 4栋1单元501", 0, "无"),
    ("谢连生", 87, "男", "幸福里 1栋1单元201", 1, "帕金森"),
    ("邓月华", 79, "女", "幸福里 5栋2单元106", 1, "类风湿"),
    ("萧永富", 71, "男", "幸福里 3栋2单元603", 0, "无"),
    ("顾春花", 82, "女", "幸福里 6栋1单元305", 1, "高血压"),
    ("阮守义", 77, "男", "幸福里 2栋1单元402", 0, "无"),
    ("石秋萍", 85, "女", "幸福里 4栋2单元102", 1, "心衰"),
    ("姚汉生", 74, "男", "幸福里 1栋3单元505", 0, "高血脂"),
]

CHRONIC_DEVICES = "智能水表,智能电表,门磁,红外活动监测"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query(sql, args=()):
    """查询多行"""
    conn = get_conn()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def query_one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    """执行写操作，返回 lastrowid"""
    conn = get_conn()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS elders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    address TEXT,
    x REAL, y REAL,                -- 地图点位（百分比坐标，v1 用示意地图）
    live_alone INTEGER DEFAULT 1,  -- 1=独居
    chronic TEXT,
    blood_type TEXT,
    allergy TEXT,
    emergency_contact TEXT,
    emergency_phone TEXT,
    devices TEXT,                  -- 已安装设备（逗号分隔）
    risk_level TEXT DEFAULT 'green',
    last_checkin TEXT,
    next_visit_due TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER,
    day TEXT,
    checkin INTEGER DEFAULT 0,
    door INTEGER DEFAULT 0,        -- 门磁开门次数
    water REAL DEFAULT 0,          -- 用水（升）
    power REAL DEFAULT 0,          -- 用电（度）
    active REAL DEFAULT 0,         -- 红外活跃小时
    score REAL DEFAULT 0           -- 活跃度指数 0-100
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    elder_id INTEGER,
    level TEXT,                    -- green/yellow/red
    trigger_type TEXT,             -- no_checkin/low_activity/sos/device_offline/manual
    reason TEXT,
    created_at TEXT,
    status TEXT DEFAULT 'pending', -- pending/dispatched/processing/closed
    assignee TEXT,
    assignee_role TEXT,            -- worker/volunteer/property
    closed_at TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS needs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER,
    category TEXT,                 -- meal/medical/renovation/housekeeping
    descr TEXT,
    urgency TEXT,                  -- high/normal
    status TEXT,                   -- 待对接/已转服务/已完成
    provider TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER,
    visitor TEXT,
    visited_at TEXT,
    content TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elder_id INTEGER,
    ts TEXT,
    icon TEXT,
    text TEXT,
    kind TEXT                      -- normal/warn
);

CREATE INDEX IF NOT EXISTS idx_alert_elder ON alerts(elder_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reading ON readings(elder_id, day);
CREATE INDEX IF NOT EXISTS idx_alert_status ON alerts(status);
"""


def _ts(hours_ago=0.0):
    return (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def seed():
    """生成演示数据"""
    conn = get_conn()
    c = conn.cursor()

    # ---- 老人 ----
    for i, (name, age, gender, addr, alone, chronic) in enumerate(ELDERS_SEED, start=1):
        c.execute(
            """INSERT INTO elders
               (name, age, gender, address, x, y, live_alone, chronic, blood_type, allergy,
                emergency_contact, emergency_phone, devices, risk_level, last_checkin, next_visit_due)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                name, age, gender, addr,
                round(random.uniform(6, 94), 1), round(random.uniform(8, 88), 1),
                alone, chronic,
                random.choice(["A", "B", "O", "AB"]) + "型",
                random.choice(["无", "无", "无", "青霉素"]),
                random.choice(["李伟", "张强", "王敏", "刘洋", "陈静"]),
                "138****" + str(random.randint(1000, 9999)),
                CHRONIC_DEVICES if alone else "智能水表,智能电表",
                # 风险分布：大部分绿、3 黄、1 红（王铁柱 id=12）
                "red" if i == 12 else ("yellow" if i in (5, 15, 18) else "green"),
                _ts(random.uniform(1, 20)) if i != 12 else _ts(50),  # 王铁柱两天没打卡
                (datetime.now() + timedelta(days=random.choice([-3, 0, 1, 2, 5]))).strftime("%Y-%m-%d"),
            ),
        )
    # 主角张桂芳（id=1）：今天还没打卡，交给演示者点击
    c.execute("UPDATE elders SET last_checkin=? WHERE id=1", (_ts(26),))

    # ---- 张桂芳近 7 天设备读数（供子女端图表）----
    for d in range(7):
        day = (datetime.now() - timedelta(days=6 - d)).strftime("%Y-%m-%d")
        if d == 6:  # 今天：数据还未产生
            score, door, water, power, active = 0, 0, 0, 0, 0
        else:
            door = random.randint(8, 14)
            water = round(random.uniform(80, 120), 1)
            power = round(random.uniform(1.2, 2.2), 2)
            active = round(random.uniform(9, 13), 1)
            score = round(min(100, door * 3.5 + water * 0.25 + power * 12 + active * 2.2), 1)
        c.execute(
            "INSERT INTO readings (elder_id, day, checkin, door, water, power, active, score) VALUES (?,?,?,?,?,?,?,?)",
            (1, day, 1, door, water, power, active, score),
        )

    # ---- 张桂芳今日时间轴事件 ----
    today = _today()
    timeline = [
        ("07:20", "🚪", "起床活动（门磁）", "normal"),
        ("08:00", "💊", "服用降压药 1 片", "normal"),
        ("11:30", "💧", "厨房用水 22 升", "normal"),
        ("15:02", "🛋️", "客厅活动 1.5 小时（红外）", "normal"),
    ]
    for ts, icon, text, kind in timeline:
        c.execute("INSERT INTO events (elder_id, ts, icon, text, kind) VALUES (?,?,?,?,?)",
                  (1, f"{today} {ts}", icon, text, kind))

    # ---- 预警/工单（覆盖各状态）----
    demo_alerts = [
        # (老人id, 等级, 触发类型, 原因, 小时前, 状态, 负责人, 负责人角色, 结果)
        (12, "red", "no_checkin", "未打卡 26 小时，今日用水 0L、门磁未开", 2, "pending", None, None, None),
        (5, "yellow", "low_activity", "活动指数 38，低于近 14 天均值 41%", 5, "dispatched", "王芳", "worker", None),
        (15, "yellow", "low_activity", "红外监测：今日客厅活动仅 2.1 小时", 9, "processing", "赵敏", "volunteer", None),
        (18, "red", "no_checkin", "连续 30 小时无用水记录", 26, "closed", "王芳", "worker", "上门核实：老人去女儿家小住，一切安好（误报已学习）"),
        (8, "yellow", "device_offline", "红外设备离线 14 小时", 30, "closed", "物业老周", "property", "设备电池更换完成"),
        (12, "yellow", "no_checkin", "昨日打卡推迟 6 小时", 47, "closed", "赵敏", "volunteer", "上门探访，老人午睡忘记打卡"),
    ]
    for elder_id, level, ttype, reason, hours, status, assignee, arole, result in demo_alerts:
        code = "AL-" + datetime.now().strftime("%Y%m%d") + "-%04d" % random.randint(1, 999)
        c.execute(
            """INSERT INTO alerts (code, elder_id, level, trigger_type, reason, created_at,
                                   status, assignee, assignee_role, closed_at, result)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (code, elder_id, level, ttype, reason, _ts(hours), status, assignee, arole,
             _ts(hours - 0.5) if status == "closed" else None, result),
        )

    # ---- 需求清单（三个清单之"需求清单"演示数据）----
    demo_needs = [
        (2, "meal", "午餐送餐上门（牙口不好，需软食）", "normal", "待对接", None),
        (5, "medical", "陪同前往社区医院复查血糖", "high", "已转服务", "社区卫生服务中心"),
        (15, "renovation", "卫生间加装扶手、防滑垫", "high", "已转服务", "适老化改造施工队"),
        (18, "housekeeping", "每月两次居室保洁", "normal", "待对接", None),
        (8, "meal", "每日助餐配送", "normal", "已完成", "幸福里长者食堂"),
    ]
    for elder_id, cat, descr, urg, status, provider in demo_needs:
        c.execute("INSERT INTO needs (elder_id, category, descr, urgency, status, provider) VALUES (?,?,?,?,?,?)",
                  (elder_id, cat, descr, urg, status, provider))

    # ---- 探访记录 ----
    demo_visits = [
        (12, "王芳", _ts(74), "例行探访：血压 148/90，已提醒按时服药，精神状态良好"),
        (1, "王芳", _ts(320), "例行探访：家中水电正常，老人反映膝盖偶有酸痛，已记录需求"),
        (18, "赵敏", _ts(500), "电话核实：老人暂住女儿家，已平安返回"),
    ]
    for elder_id, visitor, at, content in demo_visits:
        c.execute("INSERT INTO visits (elder_id, visitor, visited_at, content) VALUES (?,?,?,?)",
                  (elder_id, visitor, at, content))

    conn.commit()
    conn.close()


def init_db():
    """建库：表不存在则建表，无数据则写种子数据"""
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    has_data = conn.execute("SELECT COUNT(*) FROM elders").fetchone()[0]
    conn.close()
    if not has_data:
        seed()
        print("[安芯] 已初始化演示数据库 anxin.db（24 位老人 / 6 条预警工单）")


if __name__ == "__main__":
    init_db()
    print("OK")
