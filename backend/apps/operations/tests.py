import base64
import copy
import hashlib
import io
import json
import secrets
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import DatabaseError, close_old_connections, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from apps.catalog.models import QuizProduct, QuizVersion, Question, ScoringRule
from apps.checkout.models import Order
from apps.access.models import AccessCode, QuizGrant
from apps.access.services import AccessCodeService
from apps.quiz.models import QuizAttempt, Answer, CityResult, MentalAgeResult
from apps.payments.models import Payment, PaymentEvent
from apps.payments.services import store_fact, WeChatPayService
from .models import ContinueTicket, AuditEvent
from .services import confirm_manual_payment, record_manual_refund, resend_code


class FlowHelpers:
    def client_with_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.get('/api/session/')
        self.assertEqual(response.status_code, 200)
        client.credentials(HTTP_X_CSRFTOKEN=response.data['csrfToken'])
        return client

    def order(self, slug='city-quiz', client=None, key=None):
        client = client or self.client
        response = client.post('/api/orders/', {'product_slug': slug}, format='json',
                               HTTP_X_IDEMPOTENCY_KEY=key or secrets.token_hex(16))
        self.assertIn(response.status_code, (200, 201), str(response.data))
        return response.data

    def free_grant(self, slug='city-quiz', client=None):
        client = client or self.client
        order = self.order(slug, client)
        response = client.post(f'/api/orders/{order["id"]}/test-access/', {}, format='json')
        self.assertEqual(response.status_code, 200, str(response.data))
        return order, response.data

    def start(self, grant_id, client=None):
        response = (client or self.client).post(f'/api/quiz/grants/{grant_id}/start/', {}, format='json')
        self.assertIn(response.status_code, (200, 201), str(response.data))
        return response.data

    def finish(self, slug, choose=lambda q: q['options'][0]['id'], submit=True):
        order, access = self.free_grant(slug)
        attempt = self.start(access['grant']['id'])
        questions = self.client.get(f'/api/quiz/attempts/{attempt["id"]}/questions/').data
        revision = 0
        for question in questions:
            response = self.client.post(f'/api/quiz/attempts/{attempt["id"]}/answers/',
                {'question_id': question['id'], 'option_id': choose(question), 'revision': revision}, format='json')
            self.assertEqual(response.status_code, 200, str(response.data))
            revision = response.data['revision']
        attempt['revision'] = revision
        if not submit:
            return order, access, attempt, None
        response = self.client.post(f'/api/quiz/attempts/{attempt["id"]}/submit/', {'revision': revision}, format='json')
        self.assertEqual(response.status_code, 200, str(response.data))
        result = self.client.get(f'/api/quiz/results/{attempt["id"]}/')
        self.assertEqual(result.status_code, 200, str(result.data))
        return order, access, attempt, result.data


@override_settings(TEST_MODE=True, COOKIE_SECURE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class CustomerFlowTests(FlowHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('init_data', stdout=io.StringIO())

    def setUp(self):
        cache.clear()
        self.client = self.client_with_csrf()

    def test_original_question_counts_prices_and_complete_option_sets(self):
        products = self.client.get('/api/products/').data
        self.assertEqual({p['slug']: p['questionCount'] for p in products},
                         {'city-quiz': 45, 'mental-age-quiz': 30})
        self.assertTrue(all(p['price'] == 990 and p['canPurchase'] for p in products))
        for slug, count, choices in [('city-quiz', 45, 4), ('mental-age-quiz', 30, 5)]:
            _, access = self.free_grant(slug)
            attempt = self.start(access['grant']['id'])
            questions = self.client.get(f'/api/quiz/attempts/{attempt["id"]}/questions/').data
            self.assertEqual(len(questions), count)
            self.assertEqual([q['sequence'] for q in questions], list(range(1, count + 1)))
            self.assertTrue(all(len(q['options']) == choices for q in questions))
            self.assertNotIn('scoring_data', json.dumps(questions))
            original = json.loads((settings.BASE_DIR / 'content' /
                                 ('city.questions.v1.json' if slug == 'city-quiz' else 'mental.questions.v1.json')).read_text())
            self.assertEqual([q['text'] for q in questions], [q['prompt'] for q in original['questions']])

    def test_anonymous_writes_require_csrf_and_new_request_key(self):
        stranger = APIClient(enforce_csrf_checks=True)
        stranger.get('/api/session/')
        self.assertEqual(stranger.post('/api/orders/', {'product_slug': 'city-quiz'},
                                      format='json', HTTP_X_IDEMPOTENCY_KEY='12345678').status_code, 403)
        self.assertEqual(self.client.post('/api/orders/', {'product_slug': 'city-quiz'}, format='json').status_code, 400)

    def test_idempotent_orders_and_request_key_conflicts(self):
        a = self.order(key='same-key-1234')
        b = self.order(key='same-key-1234')
        self.assertEqual(a['id'], b['id'])
        other = self.client.post('/api/orders/', {'product_slug': 'mental-age-quiz'},
                                format='json', HTTP_X_IDEMPOTENCY_KEY='same-key-1234')
        self.assertEqual(other.status_code, 409)
        self.assertEqual(Order.objects.count(), 1)

    def test_test_access_cannot_fake_payment_and_qr_is_fixed(self):
        order = self.order()
        qr = self.client.get(f'/api/orders/{order["id"]}/payment-qr/')
        self.assertEqual(qr.data['imageUrl'], '/pay-qrcode.jpg')
        self.assertEqual(self.client.post(f'/api/orders/{order["id"]}/claim/', {}, format='json').status_code, 400)
        access = self.client.post(f'/api/orders/{order["id"]}/test-access/', {}, format='json')
        self.assertEqual(access.status_code, 200)
        current = Order.objects.get(pk=order['id'])
        self.assertEqual(current.status, 'testing')
        self.assertIsNone(current.paid_at)
        self.assertEqual(Payment.objects.count(), 0)
        code = AccessCode.objects.get(order=current)
        self.assertIsNone(code.code)
        self.assertNotEqual(code.encrypted_code, access.data['code'])
        self.assertEqual(AccessCodeService.plaintext(code), access.data['code'])

    def test_real_sales_require_approval_and_free_endpoint_is_server_gated(self):
        with override_settings(TEST_MODE=False):
            self.assertEqual(self.client.post('/api/orders/', {'product_slug': 'city-quiz'},
                format='json', HTTP_X_IDEMPOTENCY_KEY='sales-1234').status_code, 400)
            product = QuizProduct.objects.get(slug='city-quiz')
            product.current_version.approval_state = 'approved'
            product.current_version.save(update_fields=['approval_state'])
            order = self.order()
            self.assertFalse(order['isTest'])
            self.assertEqual(self.client.post(f'/api/orders/{order["id"]}/test-access/', {}, format='json').status_code, 403)
            current = Order.objects.get(pk=order['id'])
            with self.assertRaises(ValidationError): confirm_manual_payment(current, None)
            current.manual_reference = 'verified-receipt-123'
            current.save(update_fields=['manual_reference'])
            confirm_manual_payment(current, None)
            claim = self.client.post(f'/api/orders/{order["id"]}/claim/', {}, format='json')
            self.assertEqual(claim.status_code, 200)
            self.assertEqual(AuditEvent.objects.get().action, 'manual_payment_confirmed')

    def test_no_order_grant_attempt_answers_questions_or_result_leak(self):
        order, access, attempt, _ = self.finish('mental-age-quiz')
        stranger = self.client_with_csrf()
        paths = [f'/api/orders/{order["id"]}/', f'/api/access/grants/{access["grant"]["id"]}/',
                 f'/api/quiz/attempts/{attempt["id"]}/', f'/api/quiz/attempts/{attempt["id"]}/questions/',
                 f'/api/quiz/attempts/{attempt["id"]}/answers/', f'/api/quiz/results/{attempt["id"]}/']
        for path in paths:
            self.assertEqual(stranger.get(path).status_code, 404, path)
        for path in [f'/api/orders/{order["id"]}/claim/', f'/api/orders/{order["id"]}/test-access/',
                     f'/api/quiz/grants/{access["grant"]["id"]}/start/', f'/api/quiz/attempts/{attempt["id"]}/submit/']:
            self.assertEqual(stranger.post(path, {}, format='json').status_code, 404, path)
        self.assertEqual(self.client.get('/api/quiz/attempts/not-a-uuid/').status_code, 404)

    def test_code_reopens_same_attempt_and_result_without_new_answer_sheet(self):
        _, access, attempt, result = self.finish('mental-age-quiz')
        other = self.client_with_csrf()
        code = access['code'].lower().replace('-', ' ')
        verified = other.post('/api/access/verify/', {'code': code}, format='json')
        self.assertEqual(verified.status_code, 200)
        reopened = self.start(verified.data['id'], other)
        self.assertEqual(reopened['id'], attempt['id'])
        self.assertEqual(reopened['status'], 'submitted')
        self.assertEqual(other.get(f'/api/quiz/results/{attempt["id"]}/').data, result)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_save_revision_wrong_option_and_incomplete_submission(self):
        _, access = self.free_grant()
        attempt = self.start(access['grant']['id'])
        prefix = f'/api/quiz/attempts/{attempt["id"]}/'
        questions = self.client.get(prefix + 'questions/').data
        q = questions[0]
        payload = {'question_id': q['id'], 'option_id': q['options'][0]['id'], 'revision': 0}
        self.assertEqual(self.client.post(prefix + 'answers/', payload, format='json').status_code, 200)
        self.assertEqual(self.client.post(prefix + 'answers/', payload, format='json').status_code, 409)
        payload.update(revision=1, option_id='outside-this-question')
        self.assertEqual(self.client.post(prefix + 'answers/', payload, format='json').status_code, 400)
        self.assertEqual(self.client.post(prefix + 'submit/', {'revision': 1}, format='json').status_code, 400)
        restored = self.client.get(prefix + 'answers/').data
        self.assertEqual(restored['revision'], 1)
        self.assertEqual(restored['answers'][0]['questionId'], q['id'])

    def test_mental_low_high_and_nonordinal_scoring(self):
        rule = json.loads((settings.BASE_DIR / 'content/mental.scoring.v1.json').read_text())
        mapping = {row['question_id']: row['scores'] for row in rule['option_scores']}
        _, _, _, low = self.finish('mental-age-quiz', lambda q: min(mapping[q['id']], key=mapping[q['id']].get))
        _, _, _, high = self.finish('mental-age-quiz', lambda q: max(mapping[q['id']], key=mapping[q['id']].get))
        _, _, _, first = self.finish('mental-age-quiz')
        self.assertEqual((low['mentalAge'], high['mentalAge']), (16, 60))
        self.assertEqual(first['totalScore'], 31)
        self.assertEqual(first['mentalAge'], 16)
        self.assertTrue(all(result['contentPreview'] and result['isTest'] for result in (low, high, first)))

    def test_city_reports_use_answers_and_are_stable(self):
        _, _, first_attempt, first = self.finish('city-quiz')
        _, _, _, different = self.finish('city-quiz', lambda q: q['options'][-1]['id'])
        self.assertEqual(len(first['dimensions']), 11)
        self.assertEqual(len(first['allCandidates']), 16)
        self.assertEqual(len(first['topCandidates']), 5)
        self.assertNotEqual(first['allCandidates'], different['allCandidates'])
        self.assertTrue(all(0 <= candidate['score'] <= 100 for candidate in first['allCandidates']))
        self.assertEqual(self.client.get(f'/api/quiz/results/{first_attempt["id"]}/').data, first)

    def test_submission_is_idempotent_and_answers_immutable_in_api_and_database(self):
        _, _, attempt, result = self.finish('mental-age-quiz')
        path = f'/api/quiz/attempts/{attempt["id"]}/'
        self.assertEqual(self.client.post(path + 'submit/', {'revision': 30}, format='json').status_code, 200)
        self.assertEqual(self.client.post(path + 'answers/', {'question_id': 'q01', 'option_id': 'A', 'revision': 30}, format='json').status_code, 409)
        self.assertEqual(MentalAgeResult.objects.count(), 1)
        answer = Answer.objects.filter(attempt_id=attempt['id']).first()
        with self.assertRaises(DatabaseError), transaction.atomic():
            Answer.objects.filter(pk=answer.pk).update(option_id=answer.question.options.exclude(pk=answer.option_id).first().pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            QuizAttempt.objects.filter(pk=attempt['id']).update(status='in_progress')
        self.assertEqual(self.client.get(f'/api/quiz/results/{attempt["id"]}/').data, result)

    def test_order_version_and_published_content_cannot_be_changed(self):
        order = self.order()
        obj = Order.objects.get(pk=order['id'])
        with self.assertRaises(DatabaseError), transaction.atomic():
            Order.objects.filter(pk=obj.pk).update(amount=1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Question.objects.filter(version=obj.version).update(text='changed')
        with self.assertRaises(DatabaseError), transaction.atomic():
            ScoringRule.objects.filter(version=obj.version).update(rule_data={})
        other_version = QuizVersion.objects.create(product=obj.product, version_code='new-draft',
            questions_hash='new', scoring_hash='new')
        QuizProduct.objects.filter(pk=obj.product_id).update(current_version=other_version)
        access = self.client.post(f'/api/orders/{obj.pk}/test-access/', {}, format='json')
        self.assertEqual(access.status_code, 200)
        self.assertEqual(QuizGrant.objects.get(pk=access.data['grant']['id']).version_id, obj.version_id)

    def test_seed_is_idempotent(self):
        versions = list(QuizVersion.objects.values_list('pk', flat=True))
        call_command('init_data', stdout=io.StringIO())
        self.assertEqual(list(QuizVersion.objects.values_list('pk', flat=True)), versions)

    def test_continue_ticket_transfers_only_one_order_and_is_single_use(self):
        order, access = self.free_grant()
        response = self.client.post(f'/api/orders/{order["id"]}/continue/', {}, format='json')
        token = response.data['url'].split('#token=')[1]
        self.assertFalse(ContinueTicket.objects.filter(token_hash=token).exists())
        other = self.client_with_csrf()
        exchanged = other.post('/api/continue/exchange/', {'token': token}, format='json')
        self.assertEqual(exchanged.status_code, 200)
        self.assertEqual(other.get(f'/api/orders/{order["id"]}/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/orders/{order["id"]}/').status_code, 404)
        self.assertEqual(other.post('/api/continue/exchange/', {'token': token}, format='json').status_code, 400)

    def test_expired_continue_ticket_and_expired_test_order_are_rejected(self):
        order = self.order()
        response = self.client.post(f'/api/orders/{order["id"]}/continue/', {}, format='json')
        token = response.data['url'].split('#token=')[1]
        ContinueTicket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post('/api/continue/exchange/', {'token': token}, format='json').status_code, 400)
        Order.objects.filter(pk=order['id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(f'/api/orders/{order["id"]}/test-access/', {}, format='json').status_code, 400)

    def test_reissue_revokes_old_code_and_sessions_but_preserves_sheet(self):
        order, access = self.free_grant()
        attempt = self.start(access['grant']['id'])
        resend_code(Order.objects.get(pk=order['id']), None, None)
        self.assertEqual(self.client.get(f'/api/quiz/attempts/{attempt["id"]}/').status_code, 403)
        self.assertEqual(self.client.post('/api/access/verify/', {'code': access['code']}, format='json').status_code, 400)
        code = AccessCode.objects.get(order_id=order['id'])
        verified = self.client.post('/api/access/verify/', {'code': AccessCodeService.plaintext(code)}, format='json')
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(self.start(verified.data['id'])['id'], attempt['id'])


@override_settings(TEST_MODE=True, COOKIE_SECURE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class ConcurrencyTests(FlowHelpers, TransactionTestCase):
    def setUp(self):
        cache.clear()
        call_command('init_data', stdout=io.StringIO())
        self.client = self.client_with_csrf()

    def parallel_post(self, path, data):
        return self.parallel_requests([(path, data), (path, data)])

    def parallel_requests(self, jobs):
        cookies = copy.deepcopy(self.client.cookies)
        credentials = copy.deepcopy(self.client._credentials)
        def post(job):
            path, data = job
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                client.cookies = copy.deepcopy(cookies)
                client.credentials(**credentials)
                response = client.post(path, data, format='json')
                return response.status_code, response.data
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(post, jobs))

    def test_simultaneous_claim_and_start_create_one_code_grant_and_sheet(self):
        order, _ = self.free_grant()
        claims = self.parallel_post(f'/api/orders/{order["id"]}/claim/', {})
        self.assertEqual([row[0] for row in claims], [200, 200])
        self.assertEqual(claims[0][1]['code'], claims[1][1]['code'])
        grant_id = claims[0][1]['grantId']
        starts = self.parallel_post(f'/api/quiz/grants/{grant_id}/start/', {})
        self.assertEqual(sorted(row[0] for row in starts), [200, 201])
        self.assertEqual(AccessCode.objects.count(), 1)
        self.assertEqual(QuizGrant.objects.count(), 1)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_simultaneous_save_uses_revision_to_prevent_silent_overwrite(self):
        _, access = self.free_grant()
        attempt = self.start(access['grant']['id'])
        q = self.client.get(f'/api/quiz/attempts/{attempt["id"]}/questions/').data[0]
        saved = self.parallel_post(f'/api/quiz/attempts/{attempt["id"]}/answers/',
            {'question_id': q['id'], 'option_id': q['options'][0]['id'], 'revision': 0})
        self.assertEqual(sorted(row[0] for row in saved), [200, 409])
        self.assertEqual(Answer.objects.count(), 1)
        self.assertEqual(QuizAttempt.objects.get(pk=attempt['id']).revision, 1)

    def test_simultaneous_submission_creates_one_result(self):
        _, _, attempt, _ = self.finish('mental-age-quiz', submit=False)
        responses = self.parallel_post(f'/api/quiz/attempts/{attempt["id"]}/submit/', {'revision': 30})
        self.assertEqual([row[0] for row in responses], [200, 200])
        self.assertEqual(MentalAgeResult.objects.count(), 1)
        self.assertEqual(self.client.get(f'/api/quiz/results/{attempt["id"]}/').status_code, 200)

    def test_save_racing_submission_cannot_change_submitted_answers(self):
        _, _, attempt, _ = self.finish('mental-age-quiz', submit=False)
        path = f'/api/quiz/attempts/{attempt["id"]}/'
        q = self.client.get(path + 'questions/').data[-1]
        responses = self.parallel_requests([
            (path + 'submit/', {'revision': 30}),
            (path + 'answers/', {'question_id': q['id'], 'option_id': q['options'][-1]['id'], 'revision': 30}),
        ])
        self.assertEqual(sorted(row[0] for row in responses), [200, 409])
        obj = QuizAttempt.objects.get(pk=attempt['id'])
        if obj.status == 'in_progress':
            self.assertEqual(obj.revision, 31)
            self.assertEqual(self.client.post(path + 'submit/', {'revision': 31}, format='json').status_code, 200)
        before = list(Answer.objects.filter(attempt=obj).values_list('question_id', 'option_id'))
        self.assertEqual(self.client.post(path + 'answers/',
            {'question_id': q['id'], 'option_id': q['options'][0]['id'], 'revision': 31}, format='json').status_code, 409)
        self.assertEqual(before, list(Answer.objects.filter(attempt=obj).values_list('question_id', 'option_id')))
        self.assertEqual(MentalAgeResult.objects.count(), 1)


@override_settings(TEST_MODE=False, PAYMENT_MODE='wechat', COOKIE_SECURE=False,
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class PaymentVerificationTests(FlowHelpers, TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('init_data', stdout=io.StringIO())
        QuizVersion.objects.update(approval_state='approved')

    def setUp(self):
        cache.clear()
        self.client = self.client_with_csrf()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = Path(self.temp.name) / 'merchant.pem'
        public = Path(self.temp.name) / 'platform.pem'
        private.write_bytes(self.key.private_bytes(serialization.Encoding.PEM,
                          serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        public.write_bytes(self.key.public_key().public_bytes(serialization.Encoding.PEM,
                                                             serialization.PublicFormat.SubjectPublicKeyInfo))
        config = dict(settings.WECHAT_PAY)
        config.update(MCHID='merchant-test', APPID='app-test', API_V3_KEY='1' * 32, SERIAL_NO='merchant-serial',
                      PRIVATE_KEY_PATH=str(private), PUBLIC_KEY_PATH=str(public), PUBLIC_KEY_ID='PUB_KEY_TEST',
                      PLATFORM_CERT_PATH='', NOTIFY_URL='https://example.test/api/payments/wechat/notify/')
        self.override = override_settings(WECHAT_PAY=config)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def fact(self, order):
        return {'out_trade_no': order['id'], 'transaction_id': 'tx-' + secrets.token_hex(16),
                'mchid': 'merchant-test', 'appid': 'app-test', 'trade_state': 'SUCCESS', 'trade_type': 'NATIVE',
                'amount': {'total': 990, 'currency': 'CNY'}}

    def signed_headers(self, raw, timestamp=None):
        timestamp = timestamp or str(int(time.time()))
        nonce = secrets.token_hex(12)
        message = timestamp.encode() + b'\n' + nonce.encode() + b'\n' + raw + b'\n'
        signature = base64.b64encode(self.key.sign(message, padding.PKCS1v15(), hashes.SHA256())).decode()
        return {'HTTP_WECHATPAY_TIMESTAMP': timestamp, 'HTTP_WECHATPAY_NONCE': nonce,
                'HTTP_WECHATPAY_SIGNATURE': signature, 'HTTP_WECHATPAY_SERIAL': 'PUB_KEY_TEST'}

    def notify(self, fact, timestamp=None):
        nonce = secrets.token_hex(6)
        encrypted = AESGCM(b'1' * 32).encrypt(nonce.encode(), json.dumps(fact).encode(), b'transaction')
        body = {'id': 'event-' + secrets.token_hex(12), 'event_type': 'TRANSACTION.SUCCESS',
                'resource': {'algorithm': 'AEAD_AES_256_GCM', 'nonce': nonce, 'associated_data': 'transaction',
                             'ciphertext': base64.b64encode(encrypted).decode()}}
        raw = json.dumps(body, separators=(',', ':')).encode()
        response = self.client.post('/api/payments/wechat/notify/', raw, content_type='application/json',
                                    **self.signed_headers(raw, timestamp))
        return response, body, raw

    def test_missing_invalid_or_stale_signature_never_opens_access(self):
        order = self.order()
        self.assertEqual(self.client.post('/api/payments/wechat/notify/', {}, format='json').status_code, 401)
        response, _, _ = self.notify(self.fact(order), str(int(time.time()) - 600))
        self.assertEqual(response.status_code, 401)
        raw = b'{}'
        headers = self.signed_headers(raw)
        headers['HTTP_WECHATPAY_SIGNATURE'] = 'invalid'
        self.assertEqual(self.client.post('/api/payments/wechat/notify/', raw, content_type='application/json',
                                        **headers).status_code, 401)
        self.assertEqual(Order.objects.get(pk=order['id']).status, 'pending')
        self.assertEqual(AccessCode.objects.count(), 0)

    def test_amount_currency_merchant_and_app_are_verified(self):
        for field, value in [('amount.total', 1), ('amount.currency', 'USD'), ('mchid', 'other'), ('appid', 'other')]:
            with self.subTest(field=field):
                order = self.order()
                fact = self.fact(order)
                if field.startswith('amount.'): fact['amount'][field.split('.')[1]] = value
                else: fact[field] = value
                response, _, _ = self.notify(fact)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Order.objects.get(pk=order['id']).status, 'pending')
        self.assertEqual(AccessCode.objects.count(), 0)
        self.assertEqual(PaymentEvent.objects.filter(status='invalid').count(), 4)

    def test_verified_late_payment_is_kept_and_repeat_event_is_idempotent(self):
        order = self.order()
        Order.objects.filter(pk=order['id']).update(status='expired', expires_at=timezone.now() - timedelta(minutes=1))
        fact = self.fact(order)
        response, body, raw = self.notify(fact)
        self.assertEqual(response.status_code, 204)
        again = self.client.post('/api/payments/wechat/notify/', raw, content_type='application/json',
                                 **self.signed_headers(raw))
        self.assertEqual(again.status_code, 204)
        self.assertEqual(Order.objects.get(pk=order['id']).status, 'paid')
        self.assertEqual(Payment.objects.get().amount, 990)
        self.assertEqual(AccessCode.objects.count(), 1)
        self.assertEqual(QuizGrant.objects.count(), 1)
        self.assertEqual(PaymentEvent.objects.get(event_id=body['id']).status, 'processed')
        claim = self.client.post(f'/api/orders/{order["id"]}/claim/', {}, format='json')
        self.assertEqual(claim.status_code, 200)

    def test_signed_malformed_payload_is_rejected(self):
        raw = b'[]'
        response = self.client.post('/api/payments/wechat/notify/', raw, content_type='application/json',
                                   **self.signed_headers(raw))
        self.assertEqual(response.status_code, 400)
        response, _, _ = self.notify({'amount': 'invalid'})
        self.assertEqual(response.status_code, 400)

    def test_manual_refund_requires_proof_and_revokes_all_access_even_after_callback(self):
        order = self.order()
        fact = self.fact(order)
        self.assertEqual(self.notify(fact)[0].status_code, 204)
        claim = self.client.post(f'/api/orders/{order["id"]}/claim/', {}, format='json').data
        grant = self.client.post('/api/access/verify/', {'code': claim['code']}, format='json').data
        attempt = self.start(grant['id'])
        obj = Order.objects.get(pk=order['id'])
        with self.assertRaises(ValidationError): record_manual_refund(obj, None)
        obj.refund_reference = 'verified-completed-refund'
        obj.save(update_fields=['refund_reference'])
        record_manual_refund(obj, None)
        self.assertEqual(self.client.get(f'/api/quiz/attempts/{attempt["id"]}/').status_code, 403)
        self.assertEqual(self.client.post('/api/access/verify/', {'code': claim['code']}, format='json').status_code, 400)
        self.assertEqual(self.notify(fact)[0].status_code, 204)
        self.assertTrue(AccessCode.objects.get(order_id=order['id']).is_disabled)

    def test_signed_query_recovers_a_payment_when_notification_was_missed(self):
        order = self.order()
        fact = self.fact(order)
        with patch('apps.payments.services.WeChatPayClient.query_order', return_value=fact) as query:
            result = self.client.post(f'/api/orders/{order["id"]}/check-payment/', {}, format='json')
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.data['canClaim'])
            query.assert_called_once_with(order['id'])
        self.assertEqual(PaymentEvent.objects.get().source, 'query')

    def test_native_request_uses_cents_snapshot_and_exact_signed_body_and_query(self):
        import re
        from types import SimpleNamespace
        from urllib.parse import urlparse
        from apps.payments.wechat_service import WeChatPayService as PayClient
        order = self.order()
        seen = []
        def respond(method, url, data, headers, timeout):
            parsed = urlparse(url)
            path = parsed.path + ('?' + parsed.query if parsed.query else '')
            auth = headers['Authorization']
            extract = lambda key: re.search(key + '="([^"]+)"', auth).group(1)
            raw = data or b''
            signed = method.encode() + b'\n' + path.encode() + b'\n' + extract('timestamp').encode() + b'\n' + extract('nonce_str').encode() + b'\n' + raw + b'\n'
            self.key.public_key().verify(base64.b64decode(extract('signature')), signed, padding.PKCS1v15(), hashes.SHA256())
            if method == 'POST':
                payload = json.loads(raw)
                self.assertEqual(payload['amount']['total'], 990)
                self.assertEqual(payload['description'], order['productTitle'])
                result = {'code_url': 'weixin://test-only'}
            else:
                self.assertEqual(parsed.query, 'mchid=merchant-test')
                result = {'trade_state': 'NOTPAY'}
            seen.append(method)
            response_body = json.dumps(result).encode()
            response_headers = {key.removeprefix('HTTP_').replace('_', '-').title(): value
                                for key, value in self.signed_headers(response_body).items()}
            return SimpleNamespace(status_code=200, content=response_body, headers=response_headers,
                                   json=lambda: result)
        with patch('apps.payments.wechat_service.requests.request', side_effect=respond):
            self.assertEqual(WeChatPayService.create_native_payment(Order.objects.get(pk=order['id'])), 'weixin://test-only')
            self.assertEqual(PayClient().query_order(order['id'])['trade_state'], 'NOTPAY')
        self.assertEqual(seen, ['POST', 'GET'])
