from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import AccessCode, QuizGrant
from .crypto import encrypt_code, decrypt_code, lookup_hash
from apps.checkout.models import Order


def grant_data(grant):
    attempt = grant.current_attempt
    return {'id': str(grant.pk), 'productSlug': grant.product.slug,
            'productTitle': grant.access_code.order.product_title or grant.product.title,
            'productVersion': grant.version.version_code, 'status': 'available',
            'attemptStatus': attempt.status if attempt else 'not_started',
            'attemptId': str(attempt.pk) if attempt else None,
            'questionCount': grant.version.questions.count(), 'estimatedMinutes': grant.product.estimated_minutes,
            'isTest': grant.access_code.order.is_test}

class AccessCodeService:
    @staticmethod
    @transaction.atomic
    def create_access_code(order):
        order = Order.objects.select_for_update(of=('self',)).select_related('product', 'version').get(pk=order.pk)
        if not order.can_claim_access_code():
            raise ValidationError('订单尚未获得测评权限')
        existing = AccessCode.objects.filter(order=order).first()
        if existing:
            if existing.is_disabled:
                raise ValidationError('该测评权限已撤销')
            return existing
        if not order.version or not order.version.is_published:
            raise ValidationError('购买版本不可用，请联系客服')
        for _ in range(10):
            code = AccessCode.generate_code()
            hashed = lookup_hash(code)
            if not AccessCode.objects.filter(code_hash=hashed).exists():
                break
        else:
            raise ValidationError('暂时无法发放密码，请稍后重试')
        access_code = AccessCode.objects.create(order=order, product=order.product, version=order.version,
                                              code=None, encrypted_code=encrypt_code(code), code_hash=hashed)
        QuizGrant.objects.create(access_code=access_code, product=order.product, version=order.version)
        return access_code

    @staticmethod
    def plaintext(access_code):
        return decrypt_code(access_code.encrypted_code)

    @staticmethod
    def verify_access_code(code):
        try:
            hashed = lookup_hash(code)
        except ValueError:
            raise ValidationError('密码无效或当前不可用')
        with transaction.atomic():
            found = AccessCode.objects.filter(code_hash=hashed).first()
            if not found:
                raise ValidationError('密码无效或当前不可用')
            Order.objects.select_for_update().get(pk=found.order_id)
            access_code = AccessCode.objects.select_for_update(of=('self',)).select_related('order', 'grant__current_attempt',
                                    'grant__product', 'grant__version').get(pk=found.pk)
            if access_code.is_disabled or not access_code.order.can_claim_access_code():
                raise ValidationError('密码无效或当前不可用')
            access_code.activate()
            return access_code.grant
