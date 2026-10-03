import json
from cryptography.exceptions import InvalidTag
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .wechat_service import WeChatPayService
from .services import store_fact

class WeChatPaymentNotifyView(APIView):
    authentication_classes = []
    throttle_classes = []
    def post(self, request):
        if settings.PAYMENT_MODE != 'wechat':
            return Response({'code': 'FAIL', 'message': '支付通知未启用'}, status=403)
        if len(request.body) > 65536:
            return Response({'code': 'FAIL', 'message': '报文过大'}, status=400)
        client = WeChatPayService()
        if not client.verify_signature(request.headers.get('Wechatpay-Timestamp'), request.headers.get('Wechatpay-Nonce'),
                                        request.body, request.headers.get('Wechatpay-Signature'), request.headers.get('Wechatpay-Serial')):
            return Response({'code': 'FAIL', 'message': '签名无效'}, status=401)
        try:
            data = json.loads(request.body)
            if not isinstance(data, dict):
                raise ValueError('无效事件')
            if data.get('event_type') != 'TRANSACTION.SUCCESS' or not isinstance(data.get('id'), str) or not 1 <= len(data['id']) <= 100:
                raise ValueError('无效事件')
            fact = client.decrypt_callback_data(data['resource'])
            store_fact(data['id'], 'notify', fact)
        except (ValueError, KeyError, TypeError, InvalidTag, ValidationError):
            return Response({'code': 'FAIL', 'message': '通知校验失败'}, status=400)
        return Response(status=204)
