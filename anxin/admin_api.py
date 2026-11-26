"""Scoped management APIs for the multi-role care workspace."""
import csv
import io
import os
import re
import secrets
import sqlite3
import threading
import logging
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request, send_file, session
from werkzeug.security import generate_password_hash

import access_control as access
import db

bp = Blueprint('admin_api', __name__)
ROLES = {'superadmin', 'community', 'volunteer', 'family', 'elder'}
ELDER_FIELDS = ('name', 'age', 'gender', 'address', 'live_alone', 'chronic', 'allergy',
                'emergency_contact', 'emergency_phone', 'risk_level', 'next_visit_due')
DEVICE_FIELDS = ('type', 'location', 'elder_id', 'status', 'last_reading')
SERVICE_FIELDS = ('elder_id', 'category', 'title', 'status', 'assignee_id', 'assignee_name',
                  'scheduled_at', 'arrived_at', 'receipt', 'family_feedback')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
_BACKUP_THREAD = None
_BACKUP_THREAD_LOCK = threading.Lock()


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def rows(sql, args=()):
    return [dict(row) for row in db.query(sql, args)]


def row(sql, args=()):
    value = db.query_one(sql, args)
    return dict(value) if value else None


def error(message, status=400):
    return jsonify(ok=False, message=message), status


def scope_clause(alias='e'):
    return access.scope_sql(g.account, alias)


def device_scope():
    current = access.data_scope(g.account)
    if g.account['role'] == 'superadmin' or current == 'all':
        return '1=1', []
    if current == 'community':
        return 'd.community_id=?', [g.account['community_id']]
    elder_where, args = access.scope_sql(g.account, 'e')
    return f'd.elder_id IS NOT NULL AND e.id IS NOT NULL AND {elder_where}', args


def visible_elder(elder_id):
    return access.elder_accessible(g.account, elder_id)


def service_visible(service):
    if g.account['role'] == 'volunteer':
        return service.get('assignee_id') == g.account['id']
    return visible_elder(service.get('elder_id'))


def template_visible(template):
    if g.account['role'] == 'superadmin':
        return True
    return template.get('community_id') == g.account.get('community_id')


def assignee_matches_elder(assignee, elder_id):
    elder = row('SELECT community_id FROM elders WHERE id=? AND status!=\'archived\'', (elder_id,))
    return bool(elder and assignee and assignee.get('community_id') == elder['community_id'])


def safe_text(value, maximum=300):
    return isinstance(value, str) and bool(value.strip()) and len(value.strip()) <= maximum


def user_row(uid):
    return row('SELECT id,username,name,role,status,community_id,elder_id,phone,created_at,updated_at FROM users WHERE id=?', (uid,))


def in_community(user):
    scope = access.data_scope(g.account)
    if g.account['role'] == 'superadmin' or scope == 'all':
        return True
    if scope == 'community':
        return user.get('community_id') == g.account.get('community_id')
    return user.get('id') == g.account['id']


@bp.route('/api/admin/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        scope = access.data_scope(g.account)
        global_scope = g.account['role'] == 'superadmin' or scope == 'all'
        if global_scope:
            where, args = '1=1', []
        elif scope == 'community':
            where, args = 'community_id=? AND role NOT IN (\'superadmin\',\'community\')', [g.account['community_id']]
        else:
            where, args = 'id=?', [g.account['id']]
        search = request.args.get('q', '').strip()
        if search:
            where += ' AND (name LIKE ? OR username LIKE ?)'
            args += [f'%{search}%', f'%{search}%']
        return jsonify(users=rows(f'''SELECT id,username,name,role,status,community_id,elder_id,phone,created_at,updated_at
                                      FROM users WHERE {where} ORDER BY id DESC''', args))

    data = request.get_json(silent=True) or {}
    username, name, role = data.get('username', '').strip(), data.get('name', '').strip(), data.get('role')
    password = data.get('password') or secrets.token_urlsafe(12)
    allowed_roles = ROLES if g.account['role'] == 'superadmin' else {'volunteer', 'family', 'elder'}
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,80}', username) or not safe_text(name, 80) or role not in allowed_roles:
        return error('请填写有效账号、姓名和可分配角色')
    minimum = int((row("SELECT value FROM system_config WHERE key='password_min_length'") or {'value': '10'})['value'])
    if len(password) < minimum or len(password) > 200:
        return error(f'初始密码至少 {minimum} 位')
    community_id = data.get('community_id') if g.account['role'] == 'superadmin' else g.account['community_id']
    elder_id = data.get('elder_id')
    if elder_id and (role != 'elder' or not visible_elder(elder_id)):
        return error('老人账号只能绑定本范围内的老人')
    try:
        uid = db.execute('''INSERT INTO users(username,password_hash,name,role,status,community_id,elder_id,phone,created_at,updated_at)
                            VALUES(?,?,?,?,'active',?,?,?,?,?)''',
                         (username, generate_password_hash(password), name, role, community_id,
                          elder_id, data.get('phone', ''), now(), now()))
    except sqlite3.IntegrityError:
        return error('账号已存在', 409)
    return jsonify(ok=True, user=user_row(uid), temporary_password=password if not data.get('password') else None), 201


@bp.route('/api/admin/users/<int:uid>', methods=['PUT', 'PATCH'])
def update_user(uid):
    target = user_row(uid)
    if not target or not in_community(target) or target['role'] in {'superadmin', 'community'} and g.account['role'] != 'superadmin':
        return error('账号不存在或不在管理范围内', 404)
    g.audit_before = {key: target[key] for key in ('name', 'role', 'status', 'community_id', 'elder_id', 'phone')}
    data = request.get_json(silent=True) or {}
    fields = {}
    for key in ('name', 'phone', 'status'):
        if key in data:
            fields[key] = data[key]
    if 'role' in data:
        allowed_roles = ROLES if g.account['role'] == 'superadmin' else {'volunteer', 'family', 'elder'}
        if data['role'] not in allowed_roles:
            return error('无权分配此角色', 403)
        fields['role'] = data['role']
    if uid == g.account['id'] and (fields.get('status') == 'disabled' or fields.get('role') not in (None, g.account['role'])):
        return error('不能停用或更改当前登录的管理账号', 400)
    if fields.get('status') not in (None, 'active', 'disabled'):
        return error('账号状态无效')
    if fields.get('name') is not None and not safe_text(fields['name'], 80):
        return error('姓名不能为空且最多 80 字')
    if 'elder_id' in data:
        if data['elder_id'] and (target['role'] != 'elder' or not visible_elder(data['elder_id'])):
            return error('老人账号只能绑定本范围内的老人')
        fields['elder_id'] = data['elder_id']
    elif 'role' in fields and fields['role'] != 'elder':
        fields['elder_id'] = None
    fields['updated_at'] = now()
    db.execute('UPDATE users SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), uid))
    return jsonify(ok=True, user=user_row(uid))


@bp.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def delete_user(uid):
    target = user_row(uid)
    if not target or not in_community(target) or target['role'] in {'superadmin', 'community'}:
        return error('账号不存在或不允许删除', 404)
    g.audit_before = {key: target[key] for key in ('name', 'role', 'status', 'community_id')}
    db.execute("UPDATE users SET status='disabled',updated_at=? WHERE id=?", (now(), uid))
    return jsonify(ok=True, archived=True)


@bp.route('/api/admin/users/<int:uid>/reset-password', methods=['POST'])
def reset_password(uid):
    target = user_row(uid)
    if not target or not in_community(target) or target['role'] in {'superadmin', 'community'} and g.account['role'] != 'superadmin':
        return error('账号不存在或不在管理范围内', 404)
    data = request.get_json(silent=True) or {}
    password = data.get('password') or secrets.token_urlsafe(12)
    minimum = int((row("SELECT value FROM system_config WHERE key='password_min_length'") or {'value': '10'})['value'])
    if not isinstance(password, str) or len(password) < minimum or len(password) > 200:
        return error(f'密码至少 {minimum} 位且不超过 200 位')
    db.execute('UPDATE users SET password_hash=?,updated_at=? WHERE id=?',
               (generate_password_hash(password), now(), uid))
    return jsonify(ok=True, temporary_password=password if not data.get('password') else None)


@bp.route('/api/admin/elders', methods=['GET', 'POST'])
def elders():
    if request.method == 'GET':
        where, args = scope_clause()
        conditions = [where, "e.status!='archived'"]
        query_args = list(args)
        for key in ('name', 'risk_level', 'status'):
            value = request.args.get(key, '').strip()
            if value:
                conditions.append(f'e.{key} LIKE ?' if key == 'name' else f'e.{key}=?')
                query_args.append(f'%{value}%' if key == 'name' else value)
        values = rows(f'''SELECT e.* FROM elders e WHERE {' AND '.join(conditions)}
                          ORDER BY CASE risk_level WHEN 'red' THEN 0 WHEN 'yellow' THEN 1 ELSE 2 END, age DESC''', query_args)
        return jsonify(elders=values)
    data = request.get_json(silent=True) or {}
    if not safe_text(data.get('name'), 80):
        return error('老人姓名不能为空')
    fields = {key: data.get(key) for key in ELDER_FIELDS if key in data}
    fields.update(community_id=g.account.get('community_id') if g.account['role'] != 'superadmin' else data.get('community_id', 1),
                  status='active')
    names = list(fields)
    elder_id = db.execute(f"INSERT INTO elders({','.join(names)}) VALUES({','.join('?' for _ in names)})",
                          tuple(fields.values()))
    return jsonify(ok=True, elder=row('SELECT * FROM elders WHERE id=?', (elder_id,))), 201


@bp.route('/api/admin/elders/<int:elder_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def elder_detail(elder_id):
    if not visible_elder(elder_id):
        return error('老人档案不存在或不在数据范围内', 404)
    if request.method == 'GET':
        elder = row('SELECT * FROM elders WHERE id=?', (elder_id,))
        elder['alerts'] = rows('SELECT * FROM alerts WHERE elder_id=? ORDER BY created_at DESC LIMIT 20', (elder_id,))
        elder['family_links'] = rows('''SELECT f.id,f.relation,f.phone,f.emergency_contact,u.name,u.username
                                       FROM family_links f JOIN users u ON u.id=f.user_id WHERE f.elder_id=?''', (elder_id,))
        elder['services'] = rows('SELECT * FROM services WHERE elder_id=? ORDER BY created_at DESC', (elder_id,))
        return jsonify(elder=elder)
    current = row('SELECT name,age,address,chronic,allergy,risk_level,status,community_id FROM elders WHERE id=?', (elder_id,))
    g.audit_before = current or {}
    if request.method == 'DELETE':
        db.execute("UPDATE elders SET status='archived',archived_at=? WHERE id=?", (now(), elder_id))
        return jsonify(ok=True, archived=True)
    data = request.get_json(silent=True) or {}
    fields = {key: data[key] for key in ELDER_FIELDS if key in data}
    if g.account['role'] == 'superadmin' and 'community_id' in data:
        fields['community_id'] = data['community_id']
    if not fields:
        return error('没有可更新的档案字段')
    db.execute('UPDATE elders SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), elder_id))
    return jsonify(ok=True, elder=row('SELECT * FROM elders WHERE id=?', (elder_id,)))


@bp.route('/api/admin/family-links', methods=['GET', 'POST'])
def family_links():
    where, args = scope_clause()
    if request.method == 'GET':
        return jsonify(links=rows(f'''SELECT f.*,u.name AS family_name,u.username,e.name AS elder_name
                                       FROM family_links f JOIN users u ON u.id=f.user_id
                                       JOIN elders e ON e.id=f.elder_id WHERE {where}
                                       ORDER BY f.id DESC''', args))
    data = request.get_json(silent=True) or {}
    uid, elder_id = data.get('user_id'), data.get('elder_id')
    target = user_row(uid) if isinstance(uid, int) else None
    if not target or target['role'] != 'family' or not in_community(target) or not visible_elder(elder_id):
        return error('请选择本社区的家属账号和老人档案')
    try:
        link_id = db.execute('''INSERT INTO family_links(user_id,elder_id,relation,phone,emergency_contact,created_at)
                                VALUES(?,?,?,?,?,?)''', (uid, elder_id, data.get('relation', ''), data.get('phone', ''),
                                                        int(bool(data.get('emergency_contact'))), now()))
    except sqlite3.IntegrityError:
        return error('该家属已绑定这位老人', 409)
    return jsonify(ok=True, id=link_id), 201


@bp.route('/api/admin/family-links/<int:link_id>', methods=['DELETE'])
def remove_family_link(link_id):
    if request.args.get('confirm') != '1':
        return error('解绑需要二次确认', 400)
    link = row('SELECT * FROM family_links WHERE id=?', (link_id,))
    if not link or not visible_elder(link['elder_id']):
        return error('关系不存在或不在数据范围内', 404)
    g.audit_before = link
    db.execute('DELETE FROM family_links WHERE id=?', (link_id,))
    return jsonify(ok=True)


@bp.route('/api/admin/devices', methods=['GET', 'POST'])
def devices():
    if request.method == 'GET':
        where, args = device_scope()
        values = rows(f'''SELECT d.*,e.name AS elder_name FROM devices d LEFT JOIN elders e ON e.id=d.elder_id
                          WHERE d.archived_at IS NULL AND {where} ORDER BY d.id DESC''', args)
        return jsonify(devices=values)
    data = request.get_json(silent=True) or {}
    if not safe_text(data.get('type'), 80) or data.get('elder_id') and not visible_elder(data['elder_id']):
        return error('设备类型无效或老人不在数据范围内')
    code = data.get('code') or f"DEV-{secrets.token_hex(4).upper()}"
    community_id = g.account.get('community_id') or data.get('community_id', 1)
    if data.get('elder_id'):
        elder = row('SELECT community_id FROM elders WHERE id=?', (data['elder_id'],))
        community_id = elder['community_id']
    elif g.account['role'] == 'superadmin':
        community_id = data.get('community_id', 1)
    try:
        did = db.execute('''INSERT INTO devices(code,type,location,elder_id,community_id,status,last_reading,updated_at)
                            VALUES(?,?,?,?,?,?,?,?)''', (code, data['type'], data.get('location', ''), data.get('elder_id'),
                                                        community_id, data.get('status', 'online'), data.get('last_reading', ''), now()))
    except sqlite3.IntegrityError:
        return error('设备编号已存在', 409)
    return jsonify(ok=True, device=row('SELECT * FROM devices WHERE id=?', (did,))), 201


@bp.route('/api/admin/devices/<int:device_id>', methods=['GET', 'PATCH', 'PUT', 'DELETE'])
def device_detail(device_id):
    device = row('SELECT * FROM devices WHERE id=? AND archived_at IS NULL', (device_id,))
    scope = access.data_scope(g.account)
    allowed = g.account['role'] == 'superadmin' or scope == 'all'
    if device and scope == 'community':
        allowed = device['community_id'] == g.account.get('community_id')
    elif device and device['elder_id']:
        allowed = visible_elder(device['elder_id'])
    if not device or not allowed:
        return error('设备不存在或不在数据范围内', 404)
    if request.method == 'GET':
        history = rows('SELECT * FROM device_readings WHERE device_id=? ORDER BY recorded_at DESC LIMIT 100', (device_id,))
        return jsonify(device=device, history=history)
    if request.method == 'DELETE':
        g.audit_before = device
        db.execute("UPDATE devices SET status='inactive',archived_at=?,updated_at=? WHERE id=?", (now(), now(), device_id))
        return jsonify(ok=True, archived=True)
    data = request.get_json(silent=True) or {}
    g.audit_before = {key: device.get(key) for key in ('type', 'location', 'elder_id', 'community_id', 'status', 'last_reading')}
    fields = {key: data[key] for key in DEVICE_FIELDS if key in data}
    if 'elder_id' in fields and fields['elder_id'] and not visible_elder(fields['elder_id']):
        return error('老人不在数据范围内', 404)
    if 'elder_id' in fields:
        elder = row('SELECT community_id FROM elders WHERE id=?', (fields['elder_id'],)) if fields['elder_id'] else None
        fields['community_id'] = elder['community_id'] if elder else device['community_id']
    elif g.account['role'] == 'superadmin' and 'community_id' in data:
        fields['community_id'] = data['community_id']
    if not fields:
        return error('没有可更新的设备字段')
    fields['updated_at'] = now()
    db.execute('UPDATE devices SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), device_id))
    return jsonify(ok=True)


@bp.route('/api/admin/services', methods=['GET', 'POST'])
def services():
    if request.method == 'GET':
        if g.account['role'] == 'volunteer':
            conditions = ['s.archived_at IS NULL', 's.assignee_id=?']
            values = [g.account['id']]
        else:
            where, args = scope_clause()
            conditions = [where, 's.archived_at IS NULL']
            values = list(args)
        status = request.args.get('status')
        if status:
            conditions.append('s.status=?')
            values.append(status)
        return jsonify(services=rows(f'''SELECT s.*,e.name AS elder_name FROM services s
                                         JOIN elders e ON e.id=s.elder_id
                                         WHERE {' AND '.join(conditions)} ORDER BY s.scheduled_at,s.id DESC''', values))
    data = request.get_json(silent=True) or {}
    if g.account['role'] == 'volunteer':
        return error('志愿者不能创建服务任务', 403)
    if not visible_elder(data.get('elder_id')) or not safe_text(data.get('title'), 160) or not safe_text(data.get('category'), 80):
        return error('请填写有效服务内容和范围内的老人')
    fields = {key: data.get(key) for key in SERVICE_FIELDS if key in data}
    if fields.get('assignee_id'):
        try:
            assignee = user_row(int(fields['assignee_id']))
        except (TypeError, ValueError):
            assignee = None
        if not assignee or assignee['role'] != 'volunteer' or assignee['status'] != 'active':
            return error('请选择有效的志愿者账号')
        if g.account['role'] != 'superadmin' and not in_community(assignee):
            return error('志愿者不在本社区', 403)
        if not assignee_matches_elder(assignee, data.get('elder_id')):
            return error('Service and volunteer must belong to the same community', 403)
        fields['assignee_name'] = assignee['name']
    fields.setdefault('status', 'planned')
    fields.update(created_at=now(), updated_at=now())
    names = list(fields)
    sid = db.execute(f"INSERT INTO services({','.join(names)}) VALUES({','.join('?' for _ in names)})", tuple(fields.values()))
    return jsonify(ok=True, service=row('SELECT * FROM services WHERE id=?', (sid,))), 201


@bp.route('/api/admin/services/<int:service_id>', methods=['PATCH', 'PUT', 'DELETE'])
def service_detail(service_id):
    service = row('SELECT * FROM services WHERE id=? AND archived_at IS NULL', (service_id,))
    if not service or not service_visible(service):
        return error('服务不存在或不在数据范围内', 404)
    if request.method == 'DELETE':
        if g.account['role'] == 'volunteer':
            return error('志愿者不能取消服务任务', 403)
        db.execute('UPDATE services SET status=\'cancelled\',archived_at=?,updated_at=? WHERE id=?',
                   (now(), now(), service_id))
        return jsonify(ok=True, archived=True)
    data = request.get_json(silent=True) or {}
    g.audit_before = {key: service.get(key) for key in ('elder_id', 'category', 'title', 'status', 'assignee_id', 'assignee_name', 'scheduled_at', 'receipt')}
    fields = {key: data[key] for key in SERVICE_FIELDS if key in data}
    if g.account['role'] == 'volunteer':
        fields = {key: value for key, value in fields.items() if key in {'arrived_at', 'receipt', 'family_feedback', 'status'}}
        if service['assignee_id'] != g.account['id']:
            return error('只能更新分配给自己的服务', 403)
    if 'elder_id' in fields and not visible_elder(fields['elder_id']):
        return error('老人不在数据范围内', 404)
    if not fields:
        return error('没有可更新的服务字段')
    target_elder_id = fields.get('elder_id', service['elder_id'])
    if 'assignee_id' in fields and fields['assignee_id'] in ('', None):
        fields['assignee_id'] = None
        fields['assignee_name'] = ''
    candidate_assignee_id = fields.get('assignee_id', service.get('assignee_id'))
    if candidate_assignee_id:
        try:
            assignee = user_row(int(candidate_assignee_id))
        except (TypeError, ValueError):
            assignee = None
        if not assignee or assignee['role'] != 'volunteer' or assignee['status'] != 'active':
            return error('Invalid volunteer account')
        if not assignee_matches_elder(assignee, target_elder_id):
            return error('Service and volunteer must belong to the same community', 403)
        if 'assignee_id' in fields:
            fields['assignee_name'] = assignee['name']
    if g.account['role'] == 'volunteer' and 'status' in fields:
        return error('Use arrival and receipt actions to update task status', 403)
    fields['updated_at'] = now()
    db.execute('UPDATE services SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), service_id))
    return jsonify(ok=True)


@bp.route('/api/admin/services/<int:service_id>/arrival', methods=['POST'])
def service_arrival(service_id):
    service = row('SELECT * FROM services WHERE id=? AND archived_at IS NULL', (service_id,))
    if not service or not service_visible(service):
        return error('服务不存在或不在数据范围内', 404)
    if g.account['role'] == 'volunteer' and service['assignee_id'] != g.account['id']:
        return error('只能签到自己负责的任务', 403)
    g.audit_before = {'status': service['status'], 'arrived_at': service['arrived_at']}
    db.execute("UPDATE services SET status='processing',arrived_at=?,updated_at=? WHERE id=?",
               (now(), now(), service_id))
    return jsonify(ok=True, arrived_at=now())


@bp.route('/api/admin/services/<int:service_id>/complete', methods=['POST'])
def service_complete(service_id):
    service = row('SELECT * FROM services WHERE id=? AND archived_at IS NULL', (service_id,))
    data = request.get_json(silent=True) or {}
    if not service or not service_visible(service):
        return error('服务不存在或不在数据范围内', 404)
    if g.account['role'] == 'volunteer' and service['assignee_id'] != g.account['id']:
        return error('只能提交自己负责的服务回执', 403)
    if not safe_text(data.get('receipt'), 1000):
        return error('请填写服务回执')
    g.audit_before = {'status': service['status'], 'receipt': service['receipt'], 'family_feedback': service['family_feedback']}
    db.execute("UPDATE services SET status='completed',receipt=?,family_feedback=?,updated_at=? WHERE id=?",
               (data['receipt'].strip(), data.get('family_feedback', ''), now(), service_id))
    return jsonify(ok=True)


@bp.route('/api/admin/messages', methods=['GET', 'POST'])
def messages():
    if request.method == 'GET':
        user = g.account
        values = rows('''SELECT id,title,body,category,created_at,read_at FROM user_messages
                         WHERE user_id=? ORDER BY id DESC LIMIT 100''', (user['id'],))
        return jsonify(messages=values)
    data = request.get_json(silent=True) or {}
    if not safe_text(data.get('title'), 120) or not safe_text(data.get('body'), 2000):
        return error('标题和消息内容不能为空')
    target_user = data.get('user_id')
    audience = data.get('role')
    global_scope = g.account['role'] == 'superadmin' or access.data_scope(g.account) == 'all'
    community_id = g.account.get('community_id') if not global_scope else data.get('community_id')
    if target_user:
        recipient = user_row(target_user)
        if not recipient or not in_community(recipient):
            return error('收件人不在数据范围内', 404)
        recipients = [recipient['id']]
    else:
        if audience not in (*ROLES, 'all'):
            return error('请选择有效的接收角色')
        query = "SELECT id FROM users WHERE status='active' AND role!='superadmin'"
        args = []
        if audience != 'all':
            query += ' AND role=?'
            args.append(audience)
        if not global_scope:
            query += ' AND community_id=?'
            args.append(g.account['community_id'])
        elif community_id:
            query += ' AND community_id=?'
            args.append(community_id)
        recipients = [r['id'] for r in db.query(query, args)]
    conn = db.get_conn()
    try:
        conn.executemany('''INSERT INTO user_messages(user_id,audience_role,community_id,title,body,category,created_at)
                            VALUES(?,?,?,?,?,?,?)''', [(uid, audience, community_id, data['title'].strip(), data['body'].strip(),
                                                       data.get('category', 'notice'), now()) for uid in recipients])
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True, recipients=len(recipients)), 201


@bp.route('/api/admin/messages/<int:message_id>/read', methods=['POST'])
def mark_message_read(message_id):
    message = row('SELECT id FROM user_messages WHERE id=? AND user_id=?', (message_id, g.account['id']))
    if not message:
        return error('消息不存在', 404)
    db.execute('UPDATE user_messages SET read_at=COALESCE(read_at,?) WHERE id=?', (now(), message_id))
    return jsonify(ok=True)


@bp.route('/api/admin/notification-templates', methods=['GET', 'POST'])
def notification_templates():
    if request.method == 'GET':
        if g.account['role'] == 'superadmin':
            values = rows('SELECT * FROM notification_templates WHERE enabled=1 ORDER BY community_id,id DESC')
        else:
            values = rows('''SELECT * FROM notification_templates WHERE enabled=1
                             AND (community_id IS NULL OR community_id=?) ORDER BY id DESC''',
                          (g.account['community_id'],))
        return jsonify(templates=values)
    data = request.get_json(silent=True) or {}
    if not all(safe_text(data.get(key), limit) for key, limit in (('name', 80), ('title', 120), ('body', 2000))):
        return error('Template name, title and body are required')
    audience = data.get('audience_role', 'all')
    category = data.get('category', 'notice')
    if audience not in (ROLES - {'superadmin'} | {'all'}) or category not in {'notice', 'alert', 'service'}:
        return error('Invalid template audience or category')
    community_id = data.get('community_id') if g.account['role'] == 'superadmin' else g.account.get('community_id')
    if community_id is not None:
        try:
            community_id = int(community_id)
            if community_id < 1:
                raise ValueError
        except (TypeError, ValueError):
            return error('Invalid community id')
    created = now()
    template_id = db.execute('''INSERT INTO notification_templates(community_id,name,audience_role,title,body,category,created_at,updated_at)
                                VALUES(?,?,?,?,?,?,?,?)''',
                             (community_id, data['name'].strip(), audience, data['title'].strip(),
                              data['body'].strip(), category, created, created))
    return jsonify(ok=True, template=row('SELECT * FROM notification_templates WHERE id=?', (template_id,))), 201


@bp.route('/api/admin/notification-templates/<int:template_id>', methods=['PATCH', 'DELETE'])
def notification_template_detail(template_id):
    template = row('SELECT * FROM notification_templates WHERE id=? AND enabled=1', (template_id,))
    if not template or not template_visible(template):
        return error('Template not found or out of scope', 404)
    if request.method == 'DELETE':
        g.audit_before = template
        db.execute('UPDATE notification_templates SET enabled=0,updated_at=? WHERE id=?', (now(), template_id))
        return jsonify(ok=True, archived=True)
    data = request.get_json(silent=True) or {}
    fields = {key: data[key] for key in ('name', 'audience_role', 'title', 'body', 'category') if key in data}
    if (('name' in fields and not safe_text(fields['name'], 80))
            or ('title' in fields and not safe_text(fields['title'], 120))
            or ('body' in fields and not safe_text(fields['body'], 2000))):
        return error('Invalid template name, title or body')
    if (fields.get('audience_role', template['audience_role']) not in (ROLES - {'superadmin'} | {'all'})
            or fields.get('category', template['category']) not in {'notice', 'alert', 'service'}):
        return error('Invalid template audience or category')
    if not fields:
        return error('No template fields to update')
    g.audit_before = {key: template.get(key) for key in ('name', 'audience_role', 'title', 'body', 'category')}
    fields['updated_at'] = now()
    db.execute('UPDATE notification_templates SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?',
               (*fields.values(), template_id))
    return jsonify(ok=True)


@bp.route('/api/admin/audit-logs', methods=['GET'])
def audit_logs():
    scope = access.data_scope(g.account)
    if g.account['role'] == 'superadmin' or scope == 'all':
        return jsonify(logs=rows('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 500'))
    if scope == 'community':
        return jsonify(logs=rows('SELECT * FROM audit_logs WHERE community_id=? ORDER BY id DESC LIMIT 500',
                                 (g.account['community_id'],)))
    return jsonify(logs=rows('SELECT * FROM audit_logs WHERE user_id=? ORDER BY id DESC LIMIT 500', (g.account['id'],)))


@bp.route('/api/admin/roles', methods=['GET'])
def roles():
    permissions = rows('SELECT role,permission,enabled FROM role_permissions ORDER BY role,permission')
    return jsonify(roles=[{'key': role, 'permissions': [p['permission'] for p in permissions if p['role'] == role and p['enabled']],
                           'scope': access.data_scope({'role': role})}
                          for role in sorted(ROLES)], permissions=permissions)


@bp.route('/api/admin/roles/<role>/permissions', methods=['PUT'])
def update_role_permissions(role):
    if role not in ROLES:
        return error('角色不存在', 404)
    data = request.get_json(silent=True) or {}
    permissions = data.get('permissions')
    if not isinstance(permissions, list) or any(not isinstance(value, str) or len(value) > 100 for value in permissions):
        return error('权限配置格式无效')
    if role == 'superadmin' and 'system.*' not in permissions:
        return error('超级管理员必须保留系统级权限', 400)
    g.audit_before = [item['permission'] for item in rows('SELECT permission FROM role_permissions WHERE role=? AND enabled=1', (role,))]
    conn = db.get_conn()
    try:
        conn.execute('DELETE FROM role_permissions WHERE role=?', (role,))
        conn.executemany('INSERT INTO role_permissions(role,permission,enabled) VALUES(?,?,1)',
                         [(role, permission) for permission in set(permissions)])
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/api/admin/roles/<role>/scope', methods=['PUT'])
def update_role_scope(role):
    if role not in ROLES:
        return error('角色不存在', 404)
    data = request.get_json(silent=True) or {}
    scope = data.get('scope')
    allowed = {'superadmin': 'all', 'community': 'community', 'volunteer': 'assigned',
               'family': 'linked', 'elder': 'self'}
    if scope != allowed[role]:
        return error('该角色不能使用此数据范围', 400)
    before = row('SELECT scope FROM role_scopes WHERE role=?', (role,))
    g.audit_before = before or {}
    db.execute('''INSERT INTO role_scopes(role,scope) VALUES(?,?)
                  ON CONFLICT(role) DO UPDATE SET scope=excluded.scope''', (role, scope))
    return jsonify(ok=True, scope=scope)


@bp.route('/api/admin/config', methods=['GET', 'PATCH', 'PUT'])
def config():
    if request.method == 'GET':
        return jsonify(config={item['key']: item['value'] for item in rows('SELECT * FROM system_config ORDER BY key')})
    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        if key in {'last_auto_backup_at', 'last_auto_backup_attempt_at', 'last_auto_backup_error'}:
            return error('Backup status is managed by the system', 400)
        if key == 'backup_interval_hours':
            try:
                interval = int(value)
                if not 1 <= interval <= 8760:
                    raise ValueError
                data[key] = interval
            except (TypeError, ValueError):
                return error('Backup interval must be an integer from 1 to 8760 hours', 400)
    g.audit_before = {item['key']: item['value'] for item in rows('SELECT * FROM system_config')}
    conn = db.get_conn()
    try:
        for key, value in data.items():
            if not re.fullmatch(r'[a-z][a-z0-9_]{1,60}', key) or not isinstance(value, (str, int, float, bool)):
                return error('配置项格式无效')
            conn.execute('''INSERT INTO system_config(key,value,updated_at) VALUES(?,?,?)
                             ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at''',
                         (key, str(value), now()))
        conn.commit()
    finally:
        conn.close()
    return jsonify(ok=True)


@bp.route('/api/admin/dictionary', methods=['GET', 'POST'])
def dictionary():
    if request.method == 'GET':
        return jsonify(entries=rows('SELECT * FROM data_dictionary ORDER BY category,sort_order,id'))
    data = request.get_json(silent=True) or {}
    if not all(safe_text(data.get(key), 80) for key in ('category', 'code', 'label')):
        return error('字典类别、编码和名称均为必填')
    try:
        did = db.execute('INSERT INTO data_dictionary(category,code,label,sort_order) VALUES(?,?,?,?)',
                         (data['category'], data['code'], data['label'], data.get('sort_order', 0)))
    except sqlite3.IntegrityError:
        return error('该类别下的编码已存在', 409)
    return jsonify(ok=True, id=did), 201


@bp.route('/api/admin/dictionary/<int:entry_id>', methods=['PATCH', 'DELETE'])
def update_dictionary(entry_id):
    entry = row('SELECT * FROM data_dictionary WHERE id=?', (entry_id,))
    if not entry:
        return error('字典项不存在', 404)
    if request.method == 'DELETE':
        db.execute('UPDATE data_dictionary SET enabled=0 WHERE id=?', (entry_id,))
        return jsonify(ok=True)
    data = request.get_json(silent=True) or {}
    fields = {key: data[key] for key in ('label', 'enabled', 'sort_order') if key in data}
    if not fields:
        return error('没有可更新的字典字段')
    db.execute('UPDATE data_dictionary SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(), entry_id))
    return jsonify(ok=True)


def csv_response(kind, headers, data):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    for item in data:
        safe = {key: ("'" + str(item.get(key, '')) if str(item.get(key, '')).startswith(('=', '+', '-', '@')) else item.get(key, '')) for key in headers}
        writer.writerow(safe)
    from flask import Response
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="anxin-{kind}.csv"'})


@bp.route('/api/admin/export/<kind>', methods=['GET'])
def export_data(kind):
    if kind == 'elders':
        where, args = scope_clause()
        data = rows(f'SELECT e.* FROM elders e WHERE {where}', args)
        fields = list(ELDER_FIELDS) + ['id', 'community_id', 'status']
    elif kind == 'devices':
        where, args = device_scope()
        data = rows(f'''SELECT d.* FROM devices d LEFT JOIN elders e ON e.id=d.elder_id
                        WHERE d.archived_at IS NULL AND {where}''', args)
        fields = ['id', 'code', 'type', 'location', 'elder_id', 'status', 'last_reading', 'updated_at']
    elif kind == 'services':
        where, args = scope_clause()
        data = rows(f'SELECT s.* FROM services s JOIN elders e ON e.id=s.elder_id WHERE {where}', args)
        fields = list(SERVICE_FIELDS) + ['id', 'created_at', 'updated_at']
    elif kind in {'logs', 'audit'}:
        if g.account['role'] == 'superadmin' or access.data_scope(g.account) == 'all':
            data = rows('SELECT * FROM audit_logs ORDER BY id DESC')
        else:
            data = rows('SELECT * FROM audit_logs WHERE community_id=? ORDER BY id DESC', (g.account['community_id'],))
        fields = ['operator', 'role', 'community_id', 'created_at', 'module', 'action', 'object_ref',
                  'before_json', 'after_json', 'success', 'failure_reason', 'ip']
    else:
        return error('仅支持老人、设备、服务和审计数据导出', 404)
    return csv_response(kind, fields, data)


@bp.route('/api/admin/import/<kind>', methods=['POST'])
def import_data(kind):
    if kind not in {'elders', 'devices', 'services'}:
        return error('仅支持老人、设备和服务 CSV 导入', 404)
    upload = request.files.get('file')
    if not upload or not upload.filename.lower().endswith('.csv'):
        return error('请选择 CSV 文件')
    try:
        content = upload.stream.read(5_000_001)
        if len(content) > 5_000_000:
            return error('CSV 文件不能超过 5 MB')
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        records = list(reader)
    except (UnicodeDecodeError, csv.Error):
        return error('CSV 编码或格式无效')
    if not records or len(records) > 5000:
        return error('CSV 必须包含 1 至 5000 行数据')
    statements = []
    for record in records:
        if kind == 'elders':
            if not safe_text(record.get('name'), 80):
                return error('老人数据缺少有效姓名，未导入')
            fields = {key: record.get(key) for key in ELDER_FIELDS if key in record}
            try:
                community_id = g.account.get('community_id') if g.account['role'] != 'superadmin' else int(record.get('community_id') or 1)
            except (TypeError, ValueError):
                return error('社区编号格式无效，未导入')
            fields.update(community_id=community_id, status='active')
            names = list(fields)
            statements.append((f"INSERT INTO elders({','.join(names)}) VALUES({','.join('?' for _ in names)})", tuple(fields.values())))
        elif kind == 'devices':
            try:
                elder_id = int(record['elder_id']) if record.get('elder_id') else None
            except (TypeError, ValueError):
                return error('设备关联的老人编号无效，未导入')
            if not safe_text(record.get('type'), 80) or elder_id and not visible_elder(elder_id):
                return error('设备数据无效或老人不在数据范围内，未导入')
            community_id = (row('SELECT community_id FROM elders WHERE id=?', (elder_id,)) or {}).get('community_id') if elder_id else g.account.get('community_id', 1)
            statements.append(('INSERT INTO devices(code,type,location,elder_id,community_id,status,last_reading,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                               (record.get('code') or f"DEV-{secrets.token_hex(4).upper()}", record['type'], record.get('location', ''),
                                elder_id, community_id or 1, record.get('status', 'online'), record.get('last_reading', ''), now())))
        else:
            try:
                elder_id = int(record['elder_id']) if record.get('elder_id') else None
            except (TypeError, ValueError):
                return error('服务关联的老人编号无效，未导入')
            if not visible_elder(elder_id) or not safe_text(record.get('title'), 160) or not safe_text(record.get('category'), 80):
                return error('服务数据无效或老人不在数据范围内，未导入')
            assignee_id = None
            assignee_name = record.get('assignee_name', '')
            if record.get('assignee_id'):
                try:
                    assignee = user_row(int(record['assignee_id']))
                except (TypeError, ValueError):
                    assignee = None
                if not assignee or assignee['role'] != 'volunteer' or g.account['role'] != 'superadmin' and not in_community(assignee):
                    return error('服务人员不在数据范围内，未导入')
                assignee_id, assignee_name = assignee['id'], assignee['name']
            statements.append(('''INSERT INTO services(elder_id,category,title,status,assignee_id,assignee_name,scheduled_at,created_at,updated_at)
                                  VALUES(?,?,?,?,?,?,?,?,?)''',
                               (elder_id, record['category'], record['title'], record.get('status', 'planned'), assignee_id,
                                assignee_name, record.get('scheduled_at', ''), now(), now())))
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        for sql, values in statements:
            conn.execute(sql, values)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return error('数据冲突，未导入任何记录', 409)
    finally:
        conn.close()
    return jsonify(ok=True, imported=len(statements))


def backup_path(filename):
    if not re.fullmatch(r'anxin-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}\.sqlite3', filename or ''):
        return None
    path = os.path.abspath(os.path.join(BACKUP_DIR, filename))
    return path if os.path.dirname(path) == os.path.abspath(BACKUP_DIR) else None


def create_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = f"anxin-{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(4)}.sqlite3"
    target = os.path.join(BACKUP_DIR, filename)
    source_conn = sqlite3.connect(db.DB_PATH)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()
    return filename


def automatic_backup_if_due():
    current = datetime.now()
    timestamp = current.strftime('%Y-%m-%d %H:%M:%S')
    conn = db.get_conn()
    try:
        conn.execute('BEGIN IMMEDIATE')
        settings = {item['key']: item['value'] for item in conn.execute(
            "SELECT key,value FROM system_config WHERE key IN ('backup_interval_hours','last_auto_backup_at','last_auto_backup_attempt_at')").fetchall()}
        try:
            interval = max(1, min(8760, int(settings.get('backup_interval_hours') or 24)))
        except (TypeError, ValueError):
            interval = 24
        last_success = datetime.fromisoformat(settings['last_auto_backup_at']) if settings.get('last_auto_backup_at') else None
        last_attempt = datetime.fromisoformat(settings['last_auto_backup_attempt_at']) if settings.get('last_auto_backup_attempt_at') else None
        if last_success and current - last_success < timedelta(hours=interval):
            conn.rollback()
            return None
        if last_attempt and current - last_attempt < timedelta(minutes=5):
            conn.rollback()
            return None
        conn.execute('''INSERT INTO system_config(key,value,updated_at) VALUES('last_auto_backup_attempt_at',?,?)
                        ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at''',
                     (timestamp, timestamp))
        conn.commit()
    finally:
        conn.close()
    try:
        filename = create_backup()
    except Exception as exc:
        db.execute("UPDATE system_config SET value=?,updated_at=? WHERE key='last_auto_backup_error'",
                   (str(exc)[:300], timestamp))
        db.execute('''INSERT INTO audit_logs(user_id,operator,role,community_id,created_at,module,action,
                      object_ref,before_json,after_json,success,failure_reason,ip)
                      VALUES(NULL,'系统自动备份','system',NULL,?,'system','automatic_backup','', '', '',0,?,'')''',
                   (timestamp, str(exc)[:300]))
        raise
    db.execute('''INSERT INTO system_config(key,value,updated_at) VALUES('last_auto_backup_at',?,?)
                  ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at''',
               (timestamp, timestamp))
    db.execute("UPDATE system_config SET value='',updated_at=? WHERE key='last_auto_backup_error'", (timestamp,))
    db.execute('''INSERT INTO audit_logs(user_id,operator,role,community_id,created_at,module,action,
                  object_ref,before_json,after_json,success,failure_reason,ip)
                  VALUES(NULL,'系统自动备份','system',NULL,?,'system','automatic_backup',?,'','',1,'','')''',
               (timestamp, filename))
    return filename


def start_backup_monitor(check_seconds=60):
    global _BACKUP_THREAD
    with _BACKUP_THREAD_LOCK:
        if _BACKUP_THREAD and _BACKUP_THREAD.is_alive():
            return

        def run():
            while True:
                try:
                    automatic_backup_if_due()
                except Exception:
                    logging.exception('Automatic database backup failed')
                threading.Event().wait(check_seconds)

        _BACKUP_THREAD = threading.Thread(target=run, daemon=True, name='database-backup-monitor')
        _BACKUP_THREAD.start()


@bp.route('/api/admin/backups', methods=['GET', 'POST'])
def backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if request.method == 'POST':
        filename = create_backup()
        return jsonify(ok=True, backup=filename), 201
    items = []
    for filename in sorted(os.listdir(BACKUP_DIR), reverse=True):
        path = backup_path(filename)
        if path and os.path.isfile(path):
            items.append({'filename': filename, 'size': os.path.getsize(path),
                          'created_at': datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec='seconds')})
    config_values = {item['key']: item['value'] for item in rows(
        "SELECT key,value FROM system_config WHERE key IN ('backup_interval_hours','last_auto_backup_at','last_auto_backup_error')")}
    return jsonify(backups=items, schedule={
        'interval_hours': int(config_values.get('backup_interval_hours') or 24),
        'last_automatic_backup_at': config_values.get('last_auto_backup_at') or '',
        'last_error': config_values.get('last_auto_backup_error') or '',
    })


@bp.route('/api/admin/backups/<filename>', methods=['GET'])
def download_backup(filename):
    path = backup_path(filename)
    if not path or not os.path.isfile(path):
        return error('备份文件不存在', 404)
    return send_file(path, as_attachment=True, download_name=filename, mimetype='application/vnd.sqlite3')


@bp.route('/api/admin/backups/restore', methods=['POST'])
def restore_backup():
    data = request.get_json(silent=True) or {}
    filename = data.get('filename')
    path = backup_path(filename)
    if request.args.get('confirm') != '1':
        return error('恢复会替换当前数据库，需二次确认', 400)
    if not path or not os.path.isfile(path):
        return error('备份文件不存在', 404)
    check = sqlite3.connect(path)
    try:
        if not check.execute("PRAGMA quick_check").fetchone()[0] == 'ok' or not check.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
            return error('备份文件校验失败', 400)
    finally:
        check.close()
    create_backup()
    source = sqlite3.connect(path)
    destination = sqlite3.connect(db.DB_PATH)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    db.init_db()
    session.clear()
    return jsonify(ok=True, restored=filename)
