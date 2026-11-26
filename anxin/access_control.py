"""Role permissions and shared data-scope checks for API requests."""
import json

import db


API_PERMISSIONS = {
    'api_elder_home': 'elder.home',
    'api_family_overview': 'family.overview',
    'api_elders': 'elder.read',
    'api_volunteer_tasks': 'volunteer.tasks',
    'api_checkin': 'elder.checkin',
    'api_sos': 'elder.sos',
    'api_dashboard': 'dashboard.read',
    'api_alerts': 'alert.read',
    'api_alert_dispatch': 'alert.write',
    'api_alert_process': 'alert.write',
    'api_alert_close': 'alert.write',
    'api_simulator': 'alert.write',
    'read_care_notice': 'message.read',
    'demo_timeout': 'alert.write',
    'profile': 'profile.read',
    'update_profile': 'profile.write',
    'change_password': 'profile.write',
}


def endpoint_permission(endpoint, method='GET'):
    if endpoint in API_PERMISSIONS:
        if endpoint in {'api_alert_process', 'api_alert_close'} and method == 'POST':
            return 'alert.write'
        return API_PERMISSIONS[endpoint]
    if endpoint and endpoint.startswith('admin_api.'):
        action = endpoint.split('.', 1)[1]
        if action in {'roles', 'update_role_permissions', 'update_role_scope', 'config', 'dictionary', 'update_dictionary', 'backups', 'download_backup', 'restore_backup'}:
            return 'system.*'
        if action in {'users', 'update_user', 'delete_user', 'reset_password'}:
            return 'account.read' if method == 'GET' else 'account.write'
        if action in {'elders', 'elder_detail'}:
            return 'elder.read' if method == 'GET' else 'elder.write'
        if action in {'family_links', 'remove_family_link'}:
            return 'family.read' if method == 'GET' else 'family.write'
        if action in {'devices', 'device_detail'}:
            return 'device.read' if method == 'GET' else 'device.write'
        if action in {'services', 'service_detail', 'service_arrival', 'service_complete'}:
            try:
                from flask import g
                if g.account['role'] == 'volunteer':
                    return 'volunteer.tasks' if method == 'GET' else 'volunteer.task.write'
            except (AttributeError, RuntimeError, KeyError):
                pass
            return 'service.read' if method == 'GET' else 'service.write'
        if action in {'notification_templates', 'notification_template_detail'}:
            return 'message.write'
        if action in {'messages', 'mark_message_read'}:
            return 'message.read' if method == 'GET' or action == 'mark_message_read' else 'message.write'
        if action in {'audit_logs', 'export_data'}:
            return 'audit.read' if action == 'audit_logs' else 'data.export'
        if action == 'import_data':
            kind = None
            try:
                from flask import request
                kind = request.view_args.get('kind')
            except (AttributeError, RuntimeError):
                pass
            return {'elders': 'elder.write', 'devices': 'device.write', 'services': 'service.write'}.get(kind)
    return None


def permission_allowed(user, permission):
    if not user or not permission:
        return False
    row = db.query_one('SELECT enabled FROM role_permissions WHERE role=? AND permission=?',
                       (user['role'], permission))
    if row and row['enabled']:
        return True
    wildcard = db.query_one('SELECT enabled FROM role_permissions WHERE role=? AND permission=?',
                            (user['role'], 'system.*'))
    return bool(wildcard and wildcard['enabled'])


def permissions_for(role):
    return [row['permission'] for row in db.query(
        'SELECT permission FROM role_permissions WHERE role=? AND enabled=1 ORDER BY permission', (role,))]


def data_scope(user):
    # Role scopes are ceilings, not permissions that can be widened in settings.
    # Community, family, volunteer, and elder boundaries are contractual.
    return {
        'superadmin': 'all', 'community': 'community', 'volunteer': 'assigned',
        'family': 'linked', 'elder': 'self',
    }.get(user['role'], 'none')


def scope_sql(user, alias='e'):
    """Return an SQL predicate and parameters for elder-owned data."""
    scope = data_scope(user)
    if scope == 'all':
        return '1=1', []
    if scope == 'community' and user.get('community_id'):
        return f'{alias}.community_id=?', [user['community_id']]
    if scope == 'linked' and user['role'] == 'family':
        return f"{alias}.id IN (SELECT elder_id FROM family_links WHERE user_id={int(user['id'])})", []
    if scope == 'self' and user['role'] == 'elder':
        return f'{alias}.id=?', [user['elder_id']]
    return '1=0', []


def elder_accessible(user, elder_id):
    if not elder_id:
        return False
    where, args = scope_sql(user)
    return bool(db.query_one(f'SELECT e.id FROM elders e WHERE e.id=? AND {where}', [elder_id, *args]))


def alert_accessible(user, alert_id):
    row = db.query_one('''SELECT a.id,a.assignee_user_id,a.assignee,a.assignee_role,e.community_id
                          FROM alerts a LEFT JOIN elders e ON e.id=a.elder_id WHERE a.id=?''', (alert_id,))
    if not row:
        return False
    if user['role'] == 'superadmin':
        return True
    if user['role'] == 'community':
        return data_scope(user) == 'all' or row['community_id'] == user['community_id']
    if user['role'] == 'volunteer':
        return row['assignee_role'] == 'volunteer' and (
            row['assignee_user_id'] == user['id'] or row['assignee'] == user['name'])
    return False


def audit(user, module, action, object_ref='', success=True, failure_reason='', before=None, after=None, ip=''):
    if not user:
        return
    db.execute('''INSERT INTO audit_logs(user_id,operator,role,community_id,created_at,module,action,
                  object_ref,before_json,after_json,success,failure_reason,ip)
                  VALUES(?,?,?,?,datetime('now','localtime'),?,?,?,?,?,?,?,?)''',
               (user['id'], user['name'], user['role'], user.get('community_id'), module, action,
                str(object_ref or ''), json.dumps(before or {}, ensure_ascii=False),
                json.dumps(after or {}, ensure_ascii=False), int(bool(success)), failure_reason, ip))


def sanitize_payload(payload):
    if not isinstance(payload, dict):
        return {}
    return {key: value for key, value in payload.items()
            if key.lower() not in {'password', 'password_hash', 'new_password', 'current_password', 'token'}}
