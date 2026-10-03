import hashlib
import hmac
import re
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import migrations

def migrate_legacy(apps, schema_editor):
    Order = apps.get_model('checkout', 'Order')
    AccessCode = apps.get_model('access', 'AccessCode')
    cipher = Fernet(settings.CODE_ENCRYPTION_KEY.encode())
    for order in Order.objects.select_related('product'):
        code = AccessCode.objects.filter(order_id=order.pk).first()
        order.version_id = code.version_id if code else order.product.current_version_id
        order.product_title = order.product.title
        if order.status == 'refunded':
            order.refund_state = 'success'
        order.save(update_fields=['version_id', 'product_title', 'refund_state'])
    for code in AccessCode.objects.exclude(code__isnull=True).exclude(code=''):
        normalized = re.sub(r'[\s-]', '', code.code).upper()
        code.encrypted_code = cipher.encrypt(code.code.encode()).decode()
        code.code_hash = hmac.new(settings.CODE_LOOKUP_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()
        code.code = None
        code.save(update_fields=['encrypted_code', 'code_hash', 'code'])

class Migration(migrations.Migration):
    dependencies = [
        ('operations', '0001_initial'),
        ('checkout', '0003_order_refund_reference'),
        ('access', '0003_accesscode_encrypted_code_accesscode_generation_and_more'),
        ('quiz', '0002_cityresult_details_mentalageresult_details_and_more'),
    ]
    operations = [migrations.RunPython(migrate_legacy, migrations.RunPython.noop)]
