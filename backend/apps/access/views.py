from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .services import AccessCodeService, grant_data
from config.session import bind_grant, authorized_grant

class VerifyAccessCodeView(APIView):
    throttle_scope = 'access'
    def post(self, request):
        code = request.data.get('code')
        if not isinstance(code, str):
            raise ValidationError('请输入专属密码')
        grant = AccessCodeService.verify_access_code(code)
        bind_grant(request, grant.pk, grant.access_code.generation)
        return Response(grant_data(grant))

class GetGrantView(APIView):
    def get(self, request, grant_id):
        return Response(grant_data(authorized_grant(request, grant_id)))
