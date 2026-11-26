"""Production WSGI entry point for Gunicorn."""
import os


if os.environ.get('ANXIN_ENV', '').lower() == 'production':
    required = (
        'ANXIN_SECRET_KEY',
        'ANXIN_ADMIN_PASSWORD',
        'ANXIN_DEMO_PASSWORD',
        'ANXIN_DB_PATH',
        'ANXIN_BACKUP_DIR',
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError('Missing production settings: ' + ', '.join(missing))
    if len(os.environ['ANXIN_SECRET_KEY']) < 32:
        raise RuntimeError('ANXIN_SECRET_KEY must contain at least 32 characters')
    for name in ('ANXIN_ADMIN_PASSWORD', 'ANXIN_DEMO_PASSWORD'):
        if len(os.environ[name]) < 10:
            raise RuntimeError(f'{name} must contain at least 10 characters')


import care
import db
from admin_api import start_backup_monitor
from app import app


db.init_db()
care.start_monitor()
start_backup_monitor()
