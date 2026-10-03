import base64
import json
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

class WeChatPayService:
    BASE_URL = 'https://api.mch.weixin.qq.com'
    def __init__(self):
        self.config = settings.WECHAT_PAY
        self.mchid, self.appid = self.config['MCHID'], self.config['APPID']
        self.api_v3_key = self.config['API_V3_KEY']
        self.serial_no, self.notify_url = self.config['SERIAL_NO'], self.config['NOTIFY_URL']

    def verify_signature(self, timestamp, nonce, body, signature, serial=None):
        try:
            if not timestamp or not nonce or not signature or not serial or abs(time.time() - int(timestamp)) > 300:
                return False
            if len(nonce) > 128 or signature.startswith('WECHATPAY/SIGNTEST/'):
                return False
            if self.config['PUBLIC_KEY_PATH'] and serial == self.config['PUBLIC_KEY_ID']:
                with open(self.config['PUBLIC_KEY_PATH'], 'rb') as file:
                    public_key = serialization.load_pem_public_key(file.read())
            elif self.config['PLATFORM_CERT_PATH']:
                with open(self.config['PLATFORM_CERT_PATH'], 'rb') as file:
                    cert = x509.load_pem_x509_certificate(file.read())
                now = datetime.now(timezone.utc)
                if serial.upper() != format(cert.serial_number, 'X') or not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
                    return False
                public_key = cert.public_key()
            else:
                return False
            raw = body.encode() if isinstance(body, str) else body
            message = timestamp.encode() + b'\n' + nonce.encode() + b'\n' + raw + b'\n'
            public_key.verify(base64.b64decode(signature, validate=True), message, padding.PKCS1v15(), hashes.SHA256())
            return True
        except (ValueError, TypeError, OSError, KeyError):
            return False
        except Exception:
            return False

    def decrypt_callback_data(self, resource):
        if resource.get('algorithm') != 'AEAD_AES_256_GCM' or len(self.api_v3_key.encode()) != 32:
            raise ValueError('Invalid notification resource')
        raw = AESGCM(self.api_v3_key.encode()).decrypt(resource['nonce'].encode(),
            base64.b64decode(resource['ciphertext'], validate=True), resource.get('associated_data', '').encode())
        return json.loads(raw)

    def _sign(self, method, url, timestamp, nonce, body=''):
        parsed = urlparse(url)
        path = parsed.path + ('?' + parsed.query if parsed.query else '')
        message = f'{method}\n{path}\n{timestamp}\n{nonce}\n{body}\n'.encode()
        with open(self.config['PRIVATE_KEY_PATH'], 'rb') as file:
            private_key = serialization.load_pem_private_key(file.read(), password=None)
        return base64.b64encode(private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())).decode()

    def _request(self, method, path, data=None, params=None):
        if not self.mchid or not self.appid or not self.serial_no or not self.config['PRIVATE_KEY_PATH']:
            raise ValueError('微信支付配置不完整')
        url = self.BASE_URL + path + ('?' + urlencode(params) if params else '')
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')) if data is not None else ''
        timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
        signature = self._sign(method, url, timestamp, nonce, body)
        headers = {'Authorization': f'WECHATPAY2-SHA256-RSA2048 mchid="{self.mchid}",nonce_str="{nonce}",signature="{signature}",timestamp="{timestamp}",serial_no="{self.serial_no}"',
                   'Accept': 'application/json', 'Content-Type': 'application/json'}
        response = requests.request(method, url, data=body.encode() if body else None, headers=headers, timeout=10)
        if response.status_code not in (200, 204):
            raise ValueError('微信支付暂时不可用，请稍后查询原订单')
        if not self.verify_signature(response.headers.get('Wechatpay-Timestamp'), response.headers.get('Wechatpay-Nonce'),
                                     response.content, response.headers.get('Wechatpay-Signature'), response.headers.get('Wechatpay-Serial')):
            raise ValueError('微信支付响应验证失败')
        return response.json() if response.content else {}

    def create_native_payment(self, order_id, amount, description, expires_at=None):
        data = {'appid': self.appid, 'mchid': self.mchid, 'description': description, 'out_trade_no': order_id,
                'notify_url': self.notify_url, 'amount': {'total': amount, 'currency': 'CNY'}}
        if expires_at:
            data['time_expire'] = expires_at.isoformat()
        return self._request('POST', '/v3/pay/transactions/native', data)

    def create_h5_payment(self, order_id, amount, description, client_ip):
        return self._request('POST', '/v3/pay/transactions/h5', {'appid': self.appid, 'mchid': self.mchid,
            'description': description, 'out_trade_no': order_id, 'notify_url': self.notify_url,
            'amount': {'total': amount, 'currency': 'CNY'}, 'scene_info': {'payer_client_ip': client_ip, 'h5_info': {'type': 'Wap'}}})

    def query_order(self, order_id):
        return self._request('GET', f'/v3/pay/transactions/out-trade-no/{order_id}', params={'mchid': self.mchid})

    def close_order(self, order_id):
        return self._request('POST', f'/v3/pay/transactions/out-trade-no/{order_id}/close', {'mchid': self.mchid})
