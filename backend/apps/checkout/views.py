import re
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.catalog.models import QuizProduct
from apps.access.services import AccessCodeService, grant_data
from config.session import owner_token, owned_order, bind_grant
from config.errors import Conflict
from .models import Order
from .serializers import CreateOrderSerializer, OrderSerializer

class OrderViewSet(viewsets.GenericViewSet):
    serializer_class = OrderSerializer
    lookup_field = 'id'
    throttle_scope = 'orders'

    def get_throttles(self):
        self.throttle_scope = 'order_status' if self.action in ('retrieve', 'check_payment', 'payment_qr') else 'orders'
        return super().get_throttles()

    @transaction.atomic
    def create(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = request.headers.get('X-Idempotency-Key', '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', key):
            raise ValidationError('缺少有效的下单请求编号')
        token = owner_token(request)
        if not token:
            raise PermissionDenied('请刷新页面后重试')
        # Serialize this visitor's order requests, including conflicting product keys.
        Session.objects.select_for_update().filter(session_key=request.session.session_key).exists()
        existing = Order.objects.select_related('product', 'version').filter(owner_token=token, idempotency_key=key).first()
        if existing:
            if existing.product.slug != serializer.validated_data['product_slug'] or existing.source != serializer.validated_data.get('source', ''):
                raise Conflict('同一下单编号不能用于不同商品或来源')
            return Response(OrderSerializer(existing).data)
        product = QuizProduct.objects.select_for_update(of=('self',)).select_related('current_version').filter(
            slug=serializer.validated_data['product_slug'], status='published').first()
        if not product or not product.current_version or not product.current_version.is_published:
            raise ValidationError('商品暂未开放')
        version = product.current_version
        if not settings.TEST_MODE and version.approval_state != 'approved':
            raise ValidationError('该商品仍在内容审核中，暂不接受付款')
        # Recheck under the product lock when simultaneous retries raced above.
        existing = Order.objects.select_related('product', 'version').filter(owner_token=token, idempotency_key=key).first()
        if existing:
            if existing.product_id != product.pk or existing.source != serializer.validated_data.get('source', ''):
                raise Conflict('同一下单编号不能用于不同商品或来源')
            return Response(OrderSerializer(existing).data)
        if Order.objects.filter(owner_token=token, created_at__gte=timezone.now() - timedelta(days=1)).count() >= 30:
            raise ValidationError('今天创建的测评已较多，请使用已有密码继续')
        order = Order.objects.create(product=product, version=version, product_title=product.title,
            owner_token=token, idempotency_key=key, amount=product.price, currency=product.currency,
            is_test=settings.TEST_MODE, source=serializer.validated_data.get('source', ''),
            expires_at=timezone.now() + timedelta(minutes=15))
        return Response(OrderSerializer(order).data, status=201)

    def retrieve(self, request, id=None):
        order = owned_order(request, id)
        order.mark_as_expired()
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='check-payment')
    def check_payment(self, request, id=None):
        order = owned_order(request, id)
        if settings.PAYMENT_MODE == 'wechat' and not order.is_test and order.status in ('pending', 'expired'):
            from apps.payments.services import WeChatPayService
            WeChatPayService.query_order_status(order)
            order.refresh_from_db()
        order.mark_as_expired()
        return Response({'orderId': order.id, 'status': order.status, 'canClaim': order.can_claim_access_code(),
                         'message': '测试权限已开通' if order.status == 'testing' else '付款已确认' if order.status == 'paid' else '等待确认'})

    @action(detail=True, methods=['get'], url_path='payment-qr')
    def payment_qr(self, request, id=None):
        order = owned_order(request, id)
        if order.status != 'pending' or order.is_expired():
            raise ValidationError('该订单当前不接受付款')
        if settings.PAYMENT_MODE != 'wechat' or order.is_test:
            return Response({'imageUrl': settings.PAYMENT_QR_PATH, 'method': 'manual', 'testMode': order.is_test})
        from apps.payments.services import WeChatPayService
        return Response({'codeUrl': WeChatPayService.create_native_payment(order), 'method': 'native'})

    @action(detail=True, methods=['post'], url_path='claim')
    def claim_access(self, request, id=None):
        order = owned_order(request, id)
        code = AccessCodeService.create_access_code(order)
        return Response({'code': AccessCodeService.plaintext(code), 'orderId': order.id,
                         'productSlug': order.product.slug, 'productTitle': order.product_title,
                         'grantId': str(code.grant.pk), 'isTest': order.is_test})

    @action(detail=True, methods=['post'], url_path='test-access')
    @transaction.atomic
    def test_access(self, request, id=None):
        if not settings.TEST_MODE:
            raise PermissionDenied('免费测试入口未开放')
        order = owned_order(request, id, lock=True)
        if not order.is_test or order.refund_state in ('pending', 'success'):
            raise PermissionDenied('此订单不属于免费测试')
        if order.status == 'pending':
            if order.is_expired():
                raise ValidationError('测试订单已过期，请重新创建')
            order.status = 'testing'
            order.save(update_fields=['status', 'updated_at'])
        if order.status != 'testing':
            raise ValidationError('请创建新的测试测评')
        code = AccessCodeService.create_access_code(order)
        bind_grant(request, code.grant.pk)
        return Response({'grant': grant_data(code.grant), 'code': AccessCodeService.plaintext(code)})

    @action(detail=True, methods=['post'], url_path='continue')
    def continue_order(self, request, id=None):
        order = owned_order(request, id)
        from apps.operations.services import issue_ticket
        return Response(issue_ticket(order, request))
