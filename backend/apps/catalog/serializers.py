from django.conf import settings
from rest_framework import serializers
from .models import QuizProduct

class QuizProductSerializer(serializers.BaseSerializer):
    def to_representation(self, product):
        version = product.current_version
        usable = bool(version and version.is_published and (version.approval_state == 'approved' or settings.TEST_MODE))
        return {'slug': product.slug, 'title': product.title, 'description': product.description,
                'questionCount': version.questions.count() if version else 0,
                'estimatedMinutes': product.estimated_minutes, 'price': product.price, 'currency': product.currency,
                'status': product.status, 'currentVersion': version.version_code if version else '',
                'canPurchase': usable and product.status == 'published', 'testMode': settings.TEST_MODE,
                'contentPreview': bool(version and version.approval_state != 'approved')}

class QuestionSerializer(serializers.BaseSerializer):
    def to_representation(self, question):
        return {'id': question.question_id, 'sequence': question.sequence, 'dimension': question.dimension_key,
                'dimensionName': question.dimension_name, 'text': question.text,
                'options': [{'id': option.option_id, 'sequence': option.sequence, 'text': option.text}
                            for option in question.options.all()]}
