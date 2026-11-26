"""浏览器测试独立服务，不修改演示数据库。"""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
from app import app

with tempfile.TemporaryDirectory() as directory:
    db.DB_PATH = os.path.join(directory, 'browser.db')
    db.init_db()
    port = int(os.environ.get('ANXIN_TEST_PORT', '5001'))
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
