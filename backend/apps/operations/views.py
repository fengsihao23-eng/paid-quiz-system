import hashlib
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from config.session import owner_token
from apps.checkout.models import Order
from .models import ContinueTicket

class ExchangeTicketView(APIView):
    throttle_scope = 'tickets'
    @transaction.atomic
    def post(self, request):
        token = request.data.get('token')
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise ValidationError('继续链接已失效')
        seed = ContinueTicket.objects.filter(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
        if not seed:
            raise ValidationError('继续链接已失效')
        order = Order.objects.select_for_update().get(pk=seed.order_id)
        ticket = ContinueTicket.objects.select_for_update().get(pk=seed.pk)
        if not ticket or ticket.is_used or ticket.expires_at <= timezone.now():
            raise ValidationError('继续链接已失效')
        if order.refund_state in ('pending', 'success'):
            raise ValidationError('该订单权限已暂停或撤销')
        order.owner_token = owner_token(request, create=True)
        order.save(update_fields=['owner_token', 'updated_at'])
        ticket.is_used = True
        ticket.save(update_fields=['is_used'])
        return Response({'orderId': order.pk, 'canClaim': order.can_claim_access_code()})
