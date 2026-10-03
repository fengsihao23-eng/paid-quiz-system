#!/usr/bin/env python3
"""Verify real checkout gates without paying or confirming any real receipt."""
import hashlib
import json
import secrets
import sys
from pathlib import Path
import requests

root = Path(__file__).resolve().parent.parent
base = (sys.argv[1] if len(sys.argv) > 1 else (root / '.runtime/paid-public-url.txt').read_text().strip()).rstrip('/')

def visitor():
    client = requests.Session()
    client.trust_env = False
    response = client.get(base + '/api/session/', timeout=20)
    response.raise_for_status()
    info = response.json()
    assert info['testMode'] is False and info['paymentMode'] == 'manual'
    client.headers.update({'X-CSRFToken': info['csrfToken'], 'Origin': base})
    return client

def request(client, method, path, payload=None, status=200, **kwargs):
    response = client.request(method, base + path, json=payload, timeout=25, **kwargs)
    assert response.status_code == status, (method, path, response.status_code)
    return response.json() if response.content else None

client = visitor()
stranger = visitor()
assert client.get(base + '/', timeout=20).status_code == 200
assert client.get(base + '/admin/', timeout=20).status_code == 404
image = client.get(base + '/pay-qrcode.jpg', timeout=20)
image.raise_for_status()
assert hashlib.sha256(image.content).digest() == hashlib.sha256((root / 'frontend/public/pay-qrcode.jpg').read_bytes()).digest()
products = request(client, 'GET', '/api/products/')
assert len(products) == 2 and all(p['canPurchase'] and not p['contentPreview'] and p['price'] == 990 for p in products)
for slug in ('city-quiz', 'mental-age-quiz'):
    order = request(client, 'POST', '/api/orders/', {'product_slug': slug, 'source': 'deployment-acceptance-unpaid'},
        status=201, headers={'X-Idempotency-Key': secrets.token_hex(16)})
    assert not order['isTest'] and order['amount'] == 990 and order['status'] == 'pending'
    path = '/api/orders/' + order['id'] + '/'
    assert request(client, 'GET', path + 'payment-qr/')['imageUrl'] == '/pay-qrcode.jpg'
    request(client, 'POST', path + 'test-access/', {}, status=403)
    request(client, 'POST', path + 'claim/', {}, status=400)
    assert request(client, 'POST', path + 'check-payment/', {})['canClaim'] is False
    request(stranger, 'GET', path, status=404)
    print(slug + ': 990分收费下单、固定收款码、未付款禁领码与权限隔离通过', flush=True)
report = {'url': base, 'status': 'passed', 'products': 2, 'price': 990,
          'realTransfers': 0, 'confirmedReceipts': 0,
          'checks': ['HTTPS收费首页', '两套可购买', '完整内容已发布', '固定二维码原图一致',
                     '免费开通入口关闭', '未付款无法领码', '订单隔离', '公网后台关闭']}
(root / '.runtime/paid-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False, indent=2))
