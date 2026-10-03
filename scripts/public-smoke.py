#!/usr/bin/env python3
"""Exercise the deployed API, without storing browser cookies or access codes."""
import hashlib
import json
import re
import secrets
import sys
from pathlib import Path
import requests

root = Path(__file__).resolve().parent.parent
base = (sys.argv[1] if len(sys.argv) > 1 else (root / '.runtime/public-url.txt').read_text().strip()).rstrip('/')
report = {'url': base, 'checks': [], 'quizzes': []}

def visitor():
    client = requests.Session()
    client.trust_env = False
    response = client.get(base + '/api/session/', timeout=20)
    response.raise_for_status()
    client.headers.update({'X-CSRFToken': response.json()['csrfToken'], 'Origin': base})
    assert response.json()['testMode'] is True
    return client

def request(client, method, path, payload=None, status=200, **kwargs):
    response = client.request(method, base + path, json=payload, timeout=25, **kwargs)
    assert response.status_code == status, (method, path, response.status_code)
    return response.json() if response.content else None

client = visitor()
home = client.get(base + '/', timeout=20)
assert home.status_code == 200
for asset in re.findall(r'(?:src|href)="([^"]+/assets/[^"]+|/assets/[^"]+)"', home.text):
    assert client.get(base + asset, timeout=20).status_code == 200
assert client.get(base + '/admin/', timeout=20).status_code == 404
image = client.get(base + '/pay-qrcode.jpg', timeout=20)
assert image.status_code == 200
assert hashlib.sha256(image.content).digest() == hashlib.sha256((root / 'frontend/public/pay-qrcode.jpg').read_bytes()).digest()
report['checks'] += ['HTTPS首页与构建资源', '固定二维码原图一致', '公网管理后台不可访问']
stranger = visitor()
for slug, count in [('city-quiz', 45), ('mental-age-quiz', 30)]:
    order = request(client, 'POST', '/api/orders/', {'product_slug': slug, 'source': 'deployment-smoke'},
                    status=201, headers={'X-Idempotency-Key': secrets.token_hex(16)})
    assert order['amount'] == 990 and order['isTest']
    assert stranger.get(base + '/api/orders/' + order['id'] + '/', timeout=20).status_code == 404
    access = request(client, 'POST', '/api/orders/' + order['id'] + '/test-access/', {})
    grant = access['grant']
    attempt = request(client, 'POST', '/api/quiz/grants/' + grant['id'] + '/start/', {}, status=201)
    path = '/api/quiz/attempts/' + attempt['id'] + '/'
    questions = request(client, 'GET', path + 'questions/')
    assert len(questions) == count
    revision = 0
    for i, question in enumerate(questions):
        saved = request(client, 'POST', path + 'answers/',
                        {'question_id': question['id'], 'option_id': question['options'][i % len(question['options'])]['id'],
                         'revision': revision})
        revision = saved['revision']
        if i % 10 == 0: print(slug + ': 已保存 ' + str(i + 1) + '/' + str(count), flush=True)
    assert request(client, 'GET', path + 'answers/')['revision'] == count
    request(client, 'POST', path + 'submit/', {'revision': revision})
    result = request(client, 'GET', '/api/quiz/results/' + attempt['id'] + '/')
    request(client, 'POST', path + 'submit/', {'revision': revision})
    assert request(client, 'GET', '/api/quiz/results/' + attempt['id'] + '/') == result
    assert stranger.get(base + '/api/quiz/results/' + attempt['id'] + '/', timeout=20).status_code == 404
    resumed = visitor()
    verified = request(resumed, 'POST', '/api/access/verify/', {'code': access['code']})
    reopened = request(resumed, 'POST', '/api/quiz/grants/' + verified['id'] + '/start/', {})
    assert reopened['id'] == attempt['id'] and reopened['status'] == 'submitted'
    assert request(resumed, 'GET', '/api/quiz/results/' + attempt['id'] + '/') == result
    report['quizzes'].append({'product': slug, 'questionCount': count, 'savedRevision': revision,
        'status': 'passed', 'result': result['bestMatch']['cityName'] if result['type'] == 'city' else result['mentalAge']})
    print(slug + ': 公网全流程通过', flush=True)
report['checks'] += ['990分价格快照', '免付款完整答题', '提交幂等且报告一致', '新会话密码恢复同一报告', '订单与结果权限隔离']
(root / '.runtime/public-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
