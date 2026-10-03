import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError
from apps.operations.tests import FlowHelpers
from apps.operations.models import AuditEvent
from apps.operations.services import confirm_manual_payment
from apps.checkout.models import Order
from apps.access.models import AccessCode
from .models import QuizProduct, QuizVersion


@override_settings(TEST_MODE=False, PAYMENT_MODE='manual',
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PaidReleaseTests(FlowHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('init_data', stdout=io.StringIO())
        cls.operator = get_user_model().objects.create_user(username='release-operator', is_staff=True)

    def setUp(self):
        cache.clear()
        self.client = self.client_with_csrf()

    def publish(self, actor='release-operator'):
        call_command('publish_content', actor=actor, reason='UNIT TEST: entertainment publication', stdout=io.StringIO())

    def test_publication_is_validated_audited_and_idempotent(self):
        self.publish()
        self.publish()
        self.assertEqual(QuizVersion.objects.filter(approval_state='approved').count(), 2)
        self.assertEqual(AuditEvent.objects.filter(action='content_approved').count(), 2)
        products = self.client.get('/api/products/').data
        self.assertTrue(all(p['canPurchase'] and not p['testMode'] and not p['contentPreview'] for p in products))

    def test_incomplete_second_product_rolls_back_whole_publication(self):
        mental = QuizProduct.objects.get(slug='mental-age-quiz')
        incomplete = QuizVersion.objects.create(product=mental, version_code='incomplete',
            is_published=True, questions_hash='0' * 64, scoring_hash='0' * 64)
        mental.current_version = incomplete
        mental.save(update_fields=['current_version'])
        with self.assertRaises(CommandError):
            self.publish()
        self.assertFalse(QuizVersion.objects.filter(approval_state='approved').exists())
        self.assertFalse(AuditEvent.objects.filter(action='content_approved').exists())

    def test_non_staff_cannot_publish_content(self):
        get_user_model().objects.create_user(username='visitor')
        with self.assertRaises(CommandError):
            self.publish(actor='visitor')
        self.assertFalse(QuizVersion.objects.filter(approval_state='approved').exists())

    def test_same_receipt_cannot_open_two_orders(self):
        self.publish()
        first = Order.objects.get(pk=self.order('city-quiz')['id'])
        second = Order.objects.get(pk=self.order('mental-age-quiz')['id'])
        first.manual_reference = 'UNIT-TEST-UNIQUE-RECEIPT'
        first.save(update_fields=['manual_reference'])
        confirm_manual_payment(first, self.operator)
        second.manual_reference = ' UNIT-TEST-UNIQUE-RECEIPT '
        second.save(update_fields=['manual_reference'])
        with self.assertRaises(ValidationError):
            confirm_manual_payment(second, self.operator)
        second.refresh_from_db()
        self.assertEqual(second.status, 'pending')
        self.assertFalse(AccessCode.objects.filter(order=second).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.manual_reference = first.manual_reference
            second.status = 'paid'
            second.save(update_fields=['manual_reference', 'status'])

    def test_status_polling_does_not_consume_purchase_quota(self):
        self.publish()
        first = self.order('city-quiz')
        for _ in range(25):
            self.assertEqual(self.client.get(f'/api/orders/{first["id"]}/').status_code, 200)
        self.assertEqual(self.order('mental-age-quiz')['productSlug'], 'mental-age-quiz')

    def paid_flow(self, slug, count):
        self.publish()
        order = self.order(slug)
        prefix = f'/api/orders/{order["id"]}/'
        self.assertFalse(order['isTest'])
        self.assertEqual(order['amount'], 990)
        self.assertEqual(self.client.get(prefix + 'payment-qr/').data['imageUrl'], '/pay-qrcode.jpg')
        self.assertEqual(self.client.post(prefix + 'test-access/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.post(prefix + 'claim/', {}, format='json').status_code, 400)
        self.assertFalse(self.client.post(prefix + 'check-payment/', {}, format='json').data['canClaim'])
        current = Order.objects.get(pk=order['id'])
        with self.assertRaises(ValidationError):
            confirm_manual_payment(current, self.operator)
        self.assertFalse(AccessCode.objects.filter(order=current).exists())
        # Only the isolated test database records this simulated receipt; no funds move.
        current.manual_reference = 'UNIT-TEST-ONLY-NO-MONEY-MOVED'
        current.save(update_fields=['manual_reference'])
        confirm_manual_payment(current, self.operator)
        self.assertTrue(self.client.post(prefix + 'check-payment/', {}, format='json').data['canClaim'])
        claimed = self.client.post(prefix + 'claim/', {}, format='json')
        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(self.client.post(prefix + 'claim/', {}, format='json').data['code'], claimed.data['code'])
        verified = self.client.post('/api/access/verify/', {'code': claimed.data['code']}, format='json')
        self.assertEqual(verified.status_code, 200)
        attempt = self.start(verified.data['id'])
        path = f'/api/quiz/attempts/{attempt["id"]}/'
        questions = self.client.get(path + 'questions/').data
        self.assertEqual(len(questions), count)
        revision = 0
        for question in questions:
            response = self.client.post(path + 'answers/', {'question_id': question['id'],
                'option_id': question['options'][0]['id'], 'revision': revision}, format='json')
            self.assertEqual(response.status_code, 200)
            revision = response.data['revision']
        self.assertEqual(self.client.post(path + 'submit/', {'revision': revision}, format='json').status_code, 200)
        result = self.client.get(f'/api/quiz/results/{attempt["id"]}/').data
        self.assertFalse(result['isTest'])
        self.assertFalse(result['contentPreview'])
        self.assertEqual(self.client.post(path + 'submit/', {'revision': revision}, format='json').status_code, 200)
        restored = self.client_with_csrf()
        grant = restored.post('/api/access/verify/', {'code': claimed.data['code']}, format='json')
        self.assertEqual(self.start(grant.data['id'], restored)['id'], attempt['id'])
        self.assertEqual(restored.get(f'/api/quiz/results/{attempt["id"]}/').data, result)
        stranger = self.client_with_csrf()
        self.assertEqual(stranger.get(prefix).status_code, 404)
        self.assertEqual(stranger.get(f'/api/quiz/results/{attempt["id"]}/').status_code, 404)

    def test_city_paid_receipt_claim_and_full_45_question_report(self):
        self.paid_flow('city-quiz', 45)

    def test_mental_paid_receipt_claim_and_full_30_question_report(self):
        self.paid_flow('mental-age-quiz', 30)
