from rest_framework import serializers

class QuizAttemptSerializer(serializers.BaseSerializer):
    def to_representation(self, attempt):
        return {'id': str(attempt.id), 'grantId': str(attempt.grant_id), 'productSlug': attempt.product.slug,
                'totalQuestions': attempt.version.questions.count(), 'answeredCount': attempt.answers.count(),
                'status': attempt.status, 'currentQuestion': attempt.current_question, 'revision': attempt.revision,
                'submittedAt': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                'isTest': attempt.grant.access_code.order.is_test}

class AnswerSerializer(serializers.BaseSerializer):
    def to_representation(self, answer):
        return {'questionId': answer.question.question_id, 'optionId': answer.option.option_id,
                'savedAt': answer.saved_at.isoformat()}

class SaveAnswerSerializer(serializers.Serializer):
    question_id = serializers.CharField(max_length=50)
    option_id = serializers.CharField(max_length=50)
    revision = serializers.IntegerField(min_value=0)

class CityResultSerializer(serializers.BaseSerializer):
    def to_representation(self, result):
        return {'type': 'city', 'attemptId': str(result.attempt_id),
                'bestMatch': {'cityName': result.best_match_city, 'cityCode': result.best_match_code,
                              'score': result.match_index, 'matchReasons': result.match_reasons},
                'matchIndex': result.match_index, 'topCandidates': result.top_candidates,
                'dimensions': result.dimensions, 'generatedAt': result.generated_at.isoformat(), **result.details}

class MentalAgeResultSerializer(serializers.BaseSerializer):
    def to_representation(self, result):
        return {'type': 'mental-age', 'attemptId': str(result.attempt_id), 'mentalAge': result.mental_age,
                'typeName': result.type_name, 'typeDescription': result.type_description,
                'insights': result.insights, 'generatedAt': result.generated_at.isoformat(), **result.details}
