from django.middleware.csrf import get_token
from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from .session import owner_token


class SessionView(APIView):
    def get(self, request):
        owner_token(request, create=True)
        return Response({'csrfToken': get_token(request), 'testMode': settings.TEST_MODE,
                         'paymentMode': settings.PAYMENT_MODE, 'paymentQR': settings.PAYMENT_QR_PATH})


class HealthView(APIView):
    authentication_classes = []
    throttle_classes = []
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return Response({'status': 'ok'})
        except Exception:
            return Response({'status': 'unavailable'}, status=503)
