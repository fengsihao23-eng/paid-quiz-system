import hashlib
import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.catalog.models import QuizProduct, QuizVersion, Question, QuestionOption, ScoringRule


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_content(questions, rule, expected):
    if len(questions['questions']) != expected:
        raise CommandError('题量不完整')
    identities = {(q['id'], o['id']) for q in questions['questions'] for o in q['options']}
    if rule.get('algorithm') == 'dimension_normalized_city_affinity':
        rows = rule['rows']
        if {(r['question_id'], r['option_id']) for r in rows} != identities or len(rows) != len(identities):
            raise CommandError('城市评分行不完整或重复')
        city_ids = {c['id'] for c in rule['cities']}
        for row in rows:
            if set(row['affinity']) != city_ids or any(type(v) is not int or not 0 <= v <= 4 for v in row['affinity'].values()):
                raise CommandError('城市评分存在空值或非法分数')
        dimensions = {q['dimension'] for q in questions['questions']}
        if dimensions != set(rule['dimension_weights']) or any(v <= 0 for v in rule['dimension_weights'].values()):
            raise CommandError('维度权重不完整')
    else:
        scores = {(r['question_id'], key): value for r in rule['option_scores'] for key, value in r['scores'].items()}
        if set(scores) != identities or any(type(v) is not int or not 1 <= v <= 5 for v in scores.values()):
            raise CommandError('心理评分不完整')


class Command(BaseCommand):
    help = '幂等导入完整原题和娱乐测评规则；收费内容由publish_content发布'
    @transaction.atomic
    def handle(self, *args, **options):
        content = settings.BASE_DIR / 'content'
        definitions = [
            ('city-quiz', '灵魂城市测评', '从生活节奏、气候、美食与职业等 11 个维度，探索适合你的城市生活。', '6–10', 'city', 45, 'city.scoring.v1.json', 'city_affinity', {}),
            ('mental-age-quiz', '心理年龄测评', '通过 30 个生活情境，看看你的选择呈现怎样的心理年龄风格。', '4–7', 'mental', 30, 'mental.scoring.v1.json', 'mental_linear', json.loads((content / 'mental.report.v1.json').read_text())),
        ]
        for slug, title, description, minutes, source, count, rule_file, rule_type, templates in definitions:
            questions = json.loads((content / (source + '.questions.v1.json')).read_text())
            rule = json.loads((content / rule_file).read_text())
            validate_content(questions, rule, count)
            question_hash, scoring_hash = digest(questions), digest({'rule': rule, 'templates': templates})
            product, _ = QuizProduct.objects.get_or_create(slug=slug, defaults={'title': title, 'description': description,
                    'question_count': count, 'estimated_minutes': minutes, 'price': settings.PRODUCT_PRICE, 'status': 'published'})
            version_code = 'v1-' + scoring_hash[:8] + '-' + question_hash[:8]
            version, created = QuizVersion.objects.get_or_create(product=product, version_code=version_code,
                defaults={'questions_hash': question_hash, 'scoring_hash': scoring_hash, 'approval_state': 'preview',
                          'content_note': '完整娱乐测评，用于自我观察；不代表科学预测、医疗诊断或心理能力。', 'report_template': templates})
            if created:
                for q in questions['questions']:
                    question = Question.objects.create(version=version, question_id=q['id'], sequence=q['ordinal'],
                        dimension_key=q['dimension'], dimension_name=q.get('category', '心理年龄'), text=q['prompt'])
                    QuestionOption.objects.bulk_create([QuestionOption(question=question, option_id=o['id'],
                        sequence=o['ordinal'], text=o['label']) for o in q['options']])
                ScoringRule.objects.create(version=version, rule_type=rule_type, rule_data=rule)
                version.is_published = True
                version.published_at = timezone.now()
                version.save(update_fields=['is_published', 'published_at'])
            elif version.questions.count() != count or version.questions_hash != question_hash or version.scoring_hash != scoring_hash:
                raise CommandError('已存在版本与内容摘要不符，请创建新版本')
            product.title, product.description = title, description
            product.question_count, product.estimated_minutes = count, minutes
            product.price, product.status, product.current_version = settings.PRODUCT_PRICE, 'published', version
            product.save()
            self.stdout.write(f'{slug}: {count} 道原题，版本 {version_code}，审核状态 {version.approval_state}')
