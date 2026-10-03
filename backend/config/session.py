import hashlib
import secrets
from rest_framework.exceptions import NotFound, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.checkout.models import Order
from apps.access.models import QuizGrant
from apps.quiz.models import QuizAttempt


def owner_token(request, create=False):
    value = request.session.get('visitor_token')
    if not value and create:
        value = secrets.token_hex(32)
        request.session['visitor_token'] = value
    return hashlib.sha256(value.encode()).hexdigest() if value else ''


def owned_order(request, order_id, lock=False):
    token = owner_token(request)
    query = Order.objects.select_related('product', 'version')
    if lock:
        query = query.select_for_update(of=('self',))
    try:
        return query.get(id=order_id, owner_token=token) if token else _not_found()
    except Order.DoesNotExist:
        raise NotFound('订单不存在或无权访问')


def _not_found():
    raise NotFound('订单不存在或无权访问')


def bind_grant(request, grant_id, generation=None):
    grants = request.session.get('quiz_grants', {})
    if not isinstance(grants, dict):
        grants = {}
    if generation is None:
        generation = QuizGrant.objects.get(pk=grant_id).access_code.generation
    request.session['quiz_grants'] = {**grants, str(grant_id): generation}


def authorized_grant(request, grant_id, lock=False):
    if str(grant_id) not in request.session.get('quiz_grants', []):
        raise NotFound('测评不存在或无权访问，请先输入专属密码')
    query = QuizGrant.objects.select_related('access_code__order', 'product', 'version', 'current_attempt')
    if lock:
        seed = query.filter(pk=grant_id).first()
        if not seed:
            raise NotFound('测评不存在或无权访问')
        Order.objects.select_for_update().get(pk=seed.access_code.order_id)
        query = query.select_for_update(of=('self',))
    try:
        grant = query.get(pk=grant_id)
    except (QuizGrant.DoesNotExist, ValueError):
        raise NotFound('测评不存在或无权访问')
    grants = request.session.get('quiz_grants', {})
    if not isinstance(grants, dict) or grants.get(str(grant_id)) != grant.access_code.generation:
        raise PermissionDenied('登录凭证已更新，请重新输入专属密码')
    if grant.access_code.is_disabled or not grant.access_code.order.can_claim_access_code():
        raise PermissionDenied('该测评权限已暂停或撤销')
    return grant


def authorized_attempt(request, attempt_id, lock=False):
    query = QuizAttempt.objects.select_related('grant__access_code__order', 'product', 'version')
    try:
        attempt = query.get(pk=attempt_id)
    except (QuizAttempt.DoesNotExist, ValueError, DjangoValidationError):
        raise NotFound('答卷不存在或无权访问')
    authorized_grant(request, attempt.grant_id, lock=lock)
    if lock:
        attempt = query.select_for_update(of=('self',)).get(pk=attempt_id)
    return attempt
