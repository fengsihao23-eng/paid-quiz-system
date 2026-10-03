#!/usr/bin/env python3
"""Generate secrets once. The runtime files are ignored by Git."""
import base64
import argparse
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--paid', action='store_true', help='生成独立收费版配置')
paid = parser.parse_args().paid
frontend_port, admin_port = (18992, 18993) if paid else (18990, 18991)
origins = ','.join(f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (frontend_port, admin_port))
env = root / '.runtime/paid.env' if paid else root / '.env'
runtime = root / '.runtime'
runtime.mkdir(mode=0o700, exist_ok=True)
if not env.exists():
    admin_password = secrets.token_urlsafe(24)
    values = {
        'DEBUG': 'False', 'SECRET_KEY': secrets.token_urlsafe(48),
        'CODE_LOOKUP_KEY': secrets.token_urlsafe(48),
        'CODE_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'DB_PASSWORD': secrets.token_urlsafe(32),
        'TEST_MODE': 'False' if paid else 'True', 'PAYMENT_MODE': 'manual', 'PRODUCT_PRICE': '990',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,.trycloudflare.com',
        'CSRF_TRUSTED_ORIGINS': 'https://*.trycloudflare.com,' + origins,
        'COOKIE_SECURE': 'True', 'SITE_URL': '', 'FRONTEND_PORT': str(frontend_port), 'ADMIN_PORT': str(admin_port),
        'SESSION_COOKIE_NAME': 'paid_sessionid' if paid else 'sessionid',
        'CSRF_COOKIE_NAME': 'paid_csrftoken' if paid else 'csrftoken',
        'ADMIN_USERNAME': 'quizadmin', 'ADMIN_PASSWORD': admin_password,
    }
    descriptor = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write(''.join(key + '=' + value + '\n' for key, value in values.items()))
    login = runtime / ('paid-admin-login.txt' if paid else 'admin-login.txt')
    descriptor = os.open(login, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write('本机后台：http://localhost:' + values['ADMIN_PORT'] + '/admin/\n用户名：quizadmin\n密码：' + admin_password + '\n')
    print('已生成本机配置及 ' + str(login.relative_to(root)) + '，未输出任何密钥。')
else:
    print('已保留现有 ' + str(env.relative_to(root)) + ' 配置；未更换密钥或密码。')
