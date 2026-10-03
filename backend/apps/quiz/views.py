from django.db import transaction
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, NotFound
from config.session import authorized_attempt, authorized_grant
from config.errors import Conflict
from apps.catalog.models import Question, QuestionOption
from apps.catalog.serializers import QuestionSerializer
from .models import QuizAttempt, Answer, CityResult, MentalAgeResult
from .serializers import QuizAttemptSerializer, AnswerSerializer, SaveAnswerSerializer, CityResultSerializer, MentalAgeResultSerializer
from .scoring import generate_locked

class StartAttemptView(APIView):
    @transaction.atomic
    def post(self, request, grant_id):
        grant = authorized_grant(request, grant_id, lock=True)
        if grant.current_attempt:
            return Response(QuizAttemptSerializer(grant.current_attempt).data)
        attempt = QuizAttempt.objects.create(grant=grant, product=grant.product, version=grant.version)
        grant.current_attempt = attempt
        grant.save(update_fields=['current_attempt', 'updated_at'])
        return Response(QuizAttemptSerializer(attempt).data, status=201)

class QuizAttemptViewSet(viewsets.GenericViewSet):
    serializer_class = QuizAttemptSerializer
    def retrieve(self, request, pk=None):
        return Response(QuizAttemptSerializer(authorized_attempt(request, pk)).data)

    @action(detail=True, methods=['get'])
    def questions(self, request, pk=None):
        attempt = authorized_attempt(request, pk)
        questions = Question.objects.filter(version=attempt.version).prefetch_related('options').order_by('sequence')
        return Response(QuestionSerializer(questions, many=True).data)

    @action(detail=True, methods=['get', 'post'])
    def answers(self, request, pk=None):
        if request.method == 'POST':
            return self._save(request, pk)
        attempt = authorized_attempt(request, pk)
        answers = attempt.answers.select_related('question', 'option').order_by('question__sequence')
        return Response({'answers': AnswerSerializer(answers, many=True).data, 'revision': attempt.revision})

    @transaction.atomic
    def _save(self, request, pk):
        attempt = authorized_attempt(request, pk, lock=True)
        if attempt.status != 'in_progress':
            raise Conflict('答卷已经提交，不能修改')
        serializer = SaveAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if values['revision'] != attempt.revision:
            raise Conflict('答案已在其他页面更新，请重新加载后继续')
        question = Question.objects.filter(version=attempt.version, question_id=values['question_id']).first()
        option = QuestionOption.objects.filter(question=question, option_id=values['option_id']).first() if question else None
        if not question or not option:
            raise ValidationError('题目或选项不属于本答卷')
        answer, _ = Answer.objects.update_or_create(attempt=attempt, question=question, defaults={'option': option})
        attempt.revision += 1
        attempt.current_question = question.sequence
        attempt.save(update_fields=['revision', 'current_question', 'updated_at'])
        return Response({'answer': AnswerSerializer(answer).data, 'revision': attempt.revision})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        attempt = authorized_attempt(request, pk, lock=True)
        if attempt.status == 'submitted':
            generate_locked(attempt)
            return Response(QuizAttemptSerializer(attempt).data)
        revision = request.data.get('revision')
        if type(revision) is not int or revision != attempt.revision:
            raise Conflict('请等待答案保存完成，或重新加载最新答卷')
        expected = set(attempt.version.questions.values_list('pk', flat=True))
        actual = set(attempt.answers.values_list('question_id', flat=True))
        if not expected or actual != expected:
            raise ValidationError(f'还有 {len(expected - actual)} 道题未作答')
        attempt.submit()
        generate_locked(attempt)
        return Response(QuizAttemptSerializer(attempt).data)

class ResultView(APIView):
    @transaction.atomic
    def get(self, request, attempt_id, result_type=None):
        attempt = authorized_attempt(request, attempt_id, lock=True)
        if attempt.status != 'submitted':
            raise ValidationError('答卷还未提交')
        generate_locked(attempt)
        if attempt.product.slug == 'city-quiz':
            if result_type and result_type != 'city':
                raise NotFound('结果类型不匹配')
            return Response(CityResultSerializer(CityResult.objects.get(attempt=attempt)).data)
        if result_type and result_type != 'mental-age':
            raise NotFound('结果类型不匹配')
        return Response(MentalAgeResultSerializer(MentalAgeResult.objects.get(attempt=attempt)).data)
