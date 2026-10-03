#!/usr/bin/env python3
"""Generate secrets once. The runtime files are ignored by Git."""
import base64
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env = root / '.env'
runtime = root / '.runtime'
runtime.mkdir(mode=0o700, exist_ok=True)
if not env.exists():
    admin_password = secrets.token_urlsafe(24)
    values = {
        'DEBUG': 'False', 'SECRET_KEY': secrets.token_urlsafe(48),
        'CODE_LOOKUP_KEY': secrets.token_urlsafe(48),
        'CODE_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        'DB_PASSWORD': secrets.token_urlsafe(32),
        'TEST_MODE': 'True', 'PAYMENT_MODE': 'manual', 'PRODUCT_PRICE': '990',
        'ALLOWED_HOSTS': 'localhost,127.0.0.1,.trycloudflare.com',
        'CSRF_TRUSTED_ORIGINS': 'https://*.trycloudflare.com,http://localhost:18990,http://127.0.0.1:18990,http://localhost:18991,http://127.0.0.1:18991',
        'COOKIE_SECURE': 'True', 'SITE_URL': '', 'FRONTEND_PORT': '18990', 'ADMIN_PORT': '18991',
        'ADMIN_USERNAME': 'quizadmin', 'ADMIN_PASSWORD': admin_password,
    }
    descriptor = os.open(env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write(''.join(key + '=' + value + '\n' for key, value in values.items()))
    descriptor = os.open(runtime / 'admin-login.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        file.write('本机后台：http://localhost:18991/admin/\n用户名：quizadmin\n密码：' + admin_password + '\n')
    print('已生成本机配置及 .runtime/admin-login.txt，未输出任何密钥。')
else:
    print('已保留现有 .env 配置；未更换密钥或密码。')
