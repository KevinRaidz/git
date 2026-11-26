"""Demo account seed data; credentials can be overridden for deployments."""
import os
from datetime import datetime

from werkzeug.security import generate_password_hash

DEMO_PASSWORD = os.environ.get('ANXIN_DEMO_PASSWORD', 'Anxin2026!')
ADMIN_PASSWORD = os.environ.get('ANXIN_ADMIN_PASSWORD', DEMO_PASSWORD)
DEMO_USERS = [
    ('admin_demo', '系统管理员', 'superadmin'),
    ('elder_demo', '张桂芳', 'elder'),
    ('family_demo', '李伟', 'family'),
    ('community_demo', '王芳', 'community'),
    ('volunteer_demo', '赵敏', 'volunteer'),
]

ROLE_PERMISSIONS = {
    'superadmin': ['system.*'],
    'community': [
        'profile.read', 'profile.write', 'menu.community', 'dashboard.read',
        'elder.read', 'elder.write', 'alert.read', 'alert.write',
        'device.read', 'device.write', 'service.read', 'service.write',
        'message.read', 'message.write', 'account.read', 'account.write',
        'family.read', 'family.write', 'audit.read', 'data.export',
    ],
    'volunteer': ['profile.read', 'profile.write', 'menu.volunteer', 'volunteer.tasks', 'volunteer.task.write', 'message.read'],
    'family': ['profile.read', 'profile.write', 'menu.family', 'family.overview', 'message.read'],
    'elder': ['profile.read', 'profile.write', 'menu.elder', 'elder.home', 'elder.checkin', 'elder.sos', 'message.read'],
}
ROLE_SCOPES = {
    'superadmin': 'all', 'community': 'community', 'volunteer': 'assigned',
    'family': 'linked', 'elder': 'self',
}


def _ensure_column(conn, table, declaration):
    name = declaration.split()[0]
    columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}
    if name not in columns:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {declaration}')


def init_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        name TEXT NOT NULL, role TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active', community_id INTEGER DEFAULT 1,
        elder_id INTEGER, phone TEXT DEFAULT '', created_at TEXT, updated_at TEXT
    )''')
    for declaration in (
        'status TEXT NOT NULL DEFAULT \'active\'', 'community_id INTEGER DEFAULT 1',
        'elder_id INTEGER', 'phone TEXT DEFAULT \'\'', 'created_at TEXT', 'updated_at TEXT',
    ):
        _ensure_column(conn, 'users', declaration)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT NOT NULL, permission TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(role, permission)
        );
        CREATE TABLE IF NOT EXISTS role_scopes (
            role TEXT PRIMARY KEY, scope TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS family_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            elder_id INTEGER NOT NULL, relation TEXT DEFAULT '', phone TEXT DEFAULT '',
            emergency_contact INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            UNIQUE(user_id, elder_id)
        );
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL, location TEXT DEFAULT '', elder_id INTEGER,
            community_id INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'online', last_reading TEXT DEFAULT '',
            updated_at TEXT NOT NULL, archived_at TEXT
        );
        CREATE TABLE IF NOT EXISTS device_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER NOT NULL,
            value REAL, unit TEXT DEFAULT '', recorded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT, elder_id INTEGER NOT NULL,
            category TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
            assignee_id INTEGER, assignee_name TEXT DEFAULT '', scheduled_at TEXT DEFAULT '',
            arrived_at TEXT DEFAULT '', receipt TEXT DEFAULT '', family_feedback TEXT DEFAULT '',
            archived_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            audience_role TEXT, community_id INTEGER, title TEXT NOT NULL,
            body TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'notice',
            created_at TEXT NOT NULL, read_at TEXT
        );
        CREATE TABLE IF NOT EXISTS notification_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT, community_id INTEGER,
            name TEXT NOT NULL, audience_role TEXT NOT NULL DEFAULT 'all',
            title TEXT NOT NULL, body TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'notice', enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            operator TEXT NOT NULL, role TEXT NOT NULL, community_id INTEGER,
            created_at TEXT NOT NULL, module TEXT NOT NULL, action TEXT NOT NULL,
            object_ref TEXT DEFAULT '', before_json TEXT DEFAULT '', after_json TEXT DEFAULT '',
            success INTEGER NOT NULL, failure_reason TEXT DEFAULT '', ip TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS data_dictionary (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
            code TEXT NOT NULL, label TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0, UNIQUE(category, code)
        );
        CREATE INDEX IF NOT EXISTS idx_family_links_elder ON family_links(elder_id);
        CREATE INDEX IF NOT EXISTS idx_devices_elder ON devices(elder_id);
        CREATE INDEX IF NOT EXISTS idx_device_readings_history ON device_readings(device_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_services_elder ON services(elder_id, status);
        CREATE INDEX IF NOT EXISTS idx_user_messages_target ON user_messages(user_id, audience_role, community_id);
        CREATE INDEX IF NOT EXISTS idx_notification_templates_scope ON notification_templates(community_id, enabled, id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);
    ''')
    _ensure_column(conn, 'devices', 'community_id INTEGER NOT NULL DEFAULT 1')
    missing = [u for u in DEMO_USERS if not conn.execute('SELECT id FROM users WHERE username=?', (u[0],)).fetchone()]
    for username, name, role in missing:
        password = ADMIN_PASSWORD if role == 'superadmin' else DEMO_PASSWORD
        conn.execute('INSERT INTO users(username,password_hash,name,role,community_id) VALUES(?,?,?,?,1)',
                     (username, generate_password_hash(password), name, role))
    conn.execute("UPDATE users SET community_id=1 WHERE community_id IS NULL AND role IN ('community','volunteer','family','elder')")
    for role, permissions in ROLE_PERMISSIONS.items():
        for permission in permissions:
            conn.execute('INSERT OR IGNORE INTO role_permissions(role,permission,enabled) VALUES(?,?,1)',
                         (role, permission))
    for role, scope in ROLE_SCOPES.items():
        conn.execute('INSERT OR IGNORE INTO role_scopes(role,scope) VALUES(?,?)', (role, scope))
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for key, value in (('backup_interval_hours', '24'), ('last_auto_backup_at', ''),
                       ('last_auto_backup_attempt_at', ''), ('last_auto_backup_error', '')):
        conn.execute('INSERT OR IGNORE INTO system_config(key,value,updated_at) VALUES(?,?,?)',
                     (key, value, timestamp))
    if not conn.execute('SELECT 1 FROM notification_templates WHERE community_id IS NULL LIMIT 1').fetchone():
        conn.executemany('''INSERT INTO notification_templates(community_id,name,audience_role,title,body,category,created_at,updated_at)
                            VALUES(NULL,?,?,?,?,?,?,?)''', [
            ('社区服务公告', 'all', '社区服务安排', '近期服务安排已更新，请留意站内消息并联系社区确认。', 'notice', timestamp, timestamp),
            ('预警待跟进', 'community', '老人安全预警待核实', '有新的安全关注需要核实，请查看工单并及时安排跟进。', 'alert', timestamp, timestamp),
            ('服务进展通知', 'family', '老人服务进展', '老人服务已有新的进展，详情请查看家属工作台。', 'service', timestamp, timestamp),
        ])
    conn.execute("UPDATE users SET elder_id=1 WHERE username='elder_demo' AND elder_id IS NULL")
    conn.execute("UPDATE users SET created_at=COALESCE(created_at,datetime('now')), updated_at=COALESCE(updated_at,datetime('now'))")
