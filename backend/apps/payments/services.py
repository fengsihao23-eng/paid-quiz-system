from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.checkout.models import Order
from apps.access.services import AccessCodeService
from .models import Payment, PaymentEvent
from .wechat_service import WeChatPayService as WeChatPayClient


def process_event(event_id):
    try:
        with transaction.atomic():
            event = PaymentEvent.objects.select_for_update().get(pk=event_id)
            if event.status == 'processed':
                return
            fact = event.data
            if not isinstance(fact, dict) or not isinstance(fact.get('amount'), dict):
                raise ValidationError('支付事实格式无效')
            order = Order.objects.select_for_update().get(pk=fact.get('out_trade_no'))
            amount = fact.get('amount', {})
            if order.is_test or fact.get('mchid') != settings.WECHAT_PAY['MCHID'] or fact.get('appid') != settings.WECHAT_PAY['APPID']:
                raise ValidationError('支付归属不匹配')
            if type(amount.get('total')) is not int or amount['total'] != order.amount or amount.get('currency') != order.currency:
                raise ValidationError('支付金额不匹配')
            transaction_id = fact.get('transaction_id')
            if fact.get('trade_state') != 'SUCCESS' or not isinstance(transaction_id, str) or not 1 <= len(transaction_id) <= 100:
                raise ValidationError('支付事实无效')
            other = Payment.objects.filter(transaction_id=transaction_id).exclude(order=order)
            if other.exists():
                raise ValidationError('交易号归属冲突')
            payment = Payment.objects.filter(order=order, status='success').first()
            if payment and payment.transaction_id != transaction_id:
                raise ValidationError('订单已绑定另一笔交易')
            if not payment:
                method = {'NATIVE': 'native', 'H5': 'h5', 'JSAPI': 'jsapi'}.get(fact.get('trade_type'), 'native')
                payment, _ = Payment.objects.get_or_create(order=order, provider='wechat', method=method,
                    defaults={'amount': order.amount, 'currency': order.currency})
                payment.mark_as_success(transaction_id)
                payment.callback_data = fact
                payment.save(update_fields=['callback_data'])
            if order.refund_state not in ('pending', 'success'):
                AccessCodeService.create_access_code(order)
            event.status, event.error, event.processed_at = 'processed', '', timezone.now()
            event.save(update_fields=['status', 'error', 'processed_at'])
    except (ValidationError, Order.DoesNotExist) as error:
        PaymentEvent.objects.filter(pk=event_id).update(status='invalid', error=str(error)[:200])
        raise ValidationError('支付通知与订单不匹配')


def store_fact(event_id, source, fact):
    event, _ = PaymentEvent.objects.get_or_create(event_id=event_id, defaults={'source': source, 'data': fact})
    if event.data != fact:
        raise ValidationError('支付事件内容冲突')
    process_event(event.pk)


class WeChatPayService:
    @classmethod
    def create_native_payment(cls, order):
        existing = Payment.objects.filter(order=order, method='native').first()
        if existing and existing.code_url:
            return existing.code_url
        try:
            response = WeChatPayClient().create_native_payment(order.id, order.amount, order.product_title, order.expires_at)
        except (ValueError, OSError, KeyError):
            raise ValidationError('微信支付暂时不可用，请稍后查询原订单')
        if not response.get('code_url'):
            raise ValidationError('支付参数尚未就绪')
        with transaction.atomic():
            payment, _ = Payment.objects.get_or_create(order=order, provider='wechat', method='native',
                defaults={'amount': order.amount, 'currency': order.currency})
            if not payment.code_url:
                payment.code_url = response['code_url']
                payment.save(update_fields=['code_url'])
        return payment.code_url

    @classmethod
    def query_order_status(cls, order):
        try:
            response = WeChatPayClient().query_order(order.pk)
        except (ValueError, OSError) as error:
            raise ValidationError(str(error))
        if response.get('trade_state') == 'SUCCESS':
            store_fact('query-' + response['transaction_id'], 'query', response)
        return response
