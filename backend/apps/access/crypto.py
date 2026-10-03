import hashlib
import hmac
import re
from cryptography.fernet import Fernet
from django.conf import settings


def normalize_code(value):
    if not isinstance(value, str):
        raise ValueError('请输入有效的专属密码')
    normalized = re.sub(r'[\s-]', '', value).upper()
    # Accept migrated URL-safe legacy codes; new codes always have 16 unambiguous characters.
    if not re.fullmatch(r'[A-Z0-9_]{12,32}', normalized):
        raise ValueError('密码无效或当前不可用')
    return normalized


def lookup_hash(value):
    normalized = normalize_code(value)
    return hmac.new(settings.CODE_LOOKUP_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def encrypt_code(value):
    return Fernet(settings.CODE_ENCRYPTION_KEY.encode()).encrypt(value.encode()).decode()


def decrypt_code(value):
    return Fernet(settings.CODE_ENCRYPTION_KEY.encode()).decrypt(value.encode()).decode()
