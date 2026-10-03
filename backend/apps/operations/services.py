import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.checkout.models import Order
from apps.access.models import AccessCode
from apps.access.crypto import lookup_hash, encrypt_code
from apps.access.services import AccessCodeService
from .models import ContinueTicket, AuditEvent

@transaction.atomic
def issue_ticket(order, request=None):
    Order.objects.select_for_update().get(pk=order.pk)
    ContinueTicket.objects.filter(order=order, is_used=False).update(is_used=True)
    token = secrets.token_urlsafe(32)
    ContinueTicket.objects.create(order=order, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                  expires_at=timezone.now() + timedelta(minutes=5))
    base = settings.SITE_URL or (request.build_absolute_uri('/').rstrip('/') if request else '')
    return {'url': base + '/continue#token=' + token, 'expiresIn': 300}

@transaction.atomic
def confirm_manual_payment(order, actor):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_test or order.status not in ('pending', 'expired') or not order.manual_reference.strip():
        raise ValidationError('真实订单确认须填写已核对的付款凭证编号')
    order.mark_as_paid()
    AccessCodeService.create_access_code(order)
    AuditEvent.objects.create(actor=actor, order=order, action='manual_payment_confirmed',
                             details={'reference': order.manual_reference, 'amount': order.amount})

@transaction.atomic
def record_manual_refund(order, actor):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_test or order.status != 'paid' or order.refund_state == 'success' or not order.refund_reference.strip():
        raise ValidationError('须填写已完成的人工退款凭证编号，且订单为真实已付款未退款订单')
    order.refund_state = 'success'
    order.save(update_fields=['refund_state', 'updated_at'])
    AccessCode.objects.filter(order=order).update(is_disabled=True)
    ContinueTicket.objects.filter(order=order).update(is_used=True)
    AuditEvent.objects.create(actor=actor, order=order, action='manual_refund_recorded', details={'amount': order.amount, 'reference': order.refund_reference})

@transaction.atomic
def resend_code(order, actor, request):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_claim_access_code():
        raise ValidationError('该权益当前不可重发')
    code = AccessCodeService.create_access_code(order)
    code = AccessCode.objects.select_for_update().get(pk=code.pk)
    if code.is_disabled:
        raise ValidationError('已撤销的权益不能重发')
    for _ in range(10):
        raw = AccessCode.generate_code()
        hashed = lookup_hash(raw)
        if not AccessCode.objects.filter(code_hash=hashed).exists():
            break
    else:
        raise ValidationError('暂时无法重发，请稍后重试')
    code.code_hash, code.encrypted_code = hashed, encrypt_code(raw)
    code.code, code.generation = None, code.generation + 1
    code.save(update_fields=['code_hash', 'encrypted_code', 'code', 'generation', 'updated_at'])
    order.owner_token = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    order.save(update_fields=['owner_token', 'updated_at'])
    AuditEvent.objects.create(actor=actor, order=order, action='code_reissued', details={'generation': code.generation})
    return issue_ticket(order, request)
