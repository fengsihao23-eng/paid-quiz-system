from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.operations.models import AuditEvent
from .models import QuizVersion
from .management.commands.init_data import digest, validate_content


@transaction.atomic
def publish_content(version, actor, reason):
    if not actor or not actor.is_active or not actor.is_staff:
        raise ValidationError('内容发布需要有效的运营账号')
    if not reason.strip():
        raise ValidationError('请记录内容发布原因')
    version = QuizVersion.objects.select_for_update().select_related('product').get(pk=version.pk)
    expected = {'city-quiz': (45, 4), 'mental-age-quiz': (30, 5)}.get(version.product.slug)
    if not expected or not version.is_published or version.scoring_rules.count() != 1:
        raise ValidationError('须先发布完整的测评内容')
    questions = list(version.questions.prefetch_related('options'))
    if any(not q.text.strip() or q.options.count() != expected[1]
           or any(not o.text.strip() for o in q.options.all()) for q in questions):
        raise ValidationError('题目或选项内容不完整')
    identities = {'questions': [
        {'id': q.question_id, 'dimension': q.dimension_key,
         'options': [{'id': option.option_id} for option in q.options.all()]}
        for q in questions
    ]}
    rule = version.scoring_rules.get().rule_data
    validate_content(identities, rule, expected[0])
    if digest({'rule': rule, 'templates': version.report_template}) != version.scoring_hash:
        raise ValidationError('评分及报告内容与版本摘要不一致')
    if version.product.slug == 'mental-age-quiz' and len(version.report_template) != 5:
        raise ValidationError('心理年龄报告类型不完整')
    if version.approval_state == 'approved':
        return False
    version.approval_state = 'approved'
    version.save(update_fields=['approval_state'])
    AuditEvent.objects.create(actor=actor, action='content_approved', details={
        'versionId': version.pk, 'product': version.product.slug,
        'questionHash': version.questions_hash, 'scoringHash': version.scoring_hash,
        'reason': reason.strip(), 'entertainmentOnly': True,
    })
    return True
