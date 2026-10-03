from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.catalog.models import ScoringRule
from .models import QuizAttempt, CityResult, MentalAgeResult


def rounding(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def metadata(attempt):
    return {'isTest': attempt.grant.access_code.order.is_test,
            'contentPreview': attempt.version.approval_state != 'approved',
            'contentVersion': attempt.version.version_code, 'scoringHash': attempt.version.scoring_hash}


def generate_locked(attempt):
    if attempt.status != 'submitted':
        raise ValidationError('请先完成答卷')
    if attempt.result_generated:
        result_model = CityResult if attempt.product.slug == 'city-quiz' else MentalAgeResult
        if result_model.objects.filter(attempt=attempt).exists():
            return
    answers = list(attempt.answers.select_related('question', 'option').order_by('question__sequence'))
    if not answers or len(answers) != attempt.version.questions.count():
        raise ValidationError('答卷尚未完整')
    rules = list(ScoringRule.objects.filter(version=attempt.version))
    if len(rules) != 1:
        raise ValidationError('该历史版本缺少完整评分规则，请联系客服')
    rule = rules[0].rule_data
    if rule.get('algorithm') == 'dimension_normalized_city_affinity':
        affinity = {(r['question_id'], r['option_id']): r['affinity'] for r in rule['rows']}
        dimensions = defaultdict(list)
        for answer in answers:
            key = (answer.question.question_id, answer.option.option_id)
            if key not in affinity:
                raise ValidationError('评分规则不完整')
            dimensions[answer.question.dimension_key].append(affinity[key])
        weights = rule['dimension_weights']
        dimension_names = {a.question.dimension_key: a.question.dimension_name for a in answers}
        ranked = []
        for city in rule['cities']:
            per_dimension = {key: sum(row[city['id']] for row in rows) / (4 * len(rows))
                             for key, rows in dimensions.items()}
            score = sum(per_dimension[key] * weights[key] for key in per_dimension) / sum(weights[key] for key in per_dimension)
            ranked.append({'cityCode': city['id'], 'cityName': city['name'], 'emoji': city['emoji'],
                           'tags': city['tags'], 'score': rounding(score * 100), '_precise': score,
                           '_dimensions': per_dimension})
        ranked.sort(key=lambda city: (-city['_precise'], city['cityCode']))
        best = ranked[0]
        strongest = sorted(best['_dimensions'], key=lambda key: (-best['_dimensions'][key], key))[:3]
        reasons = [f'在「{dimension_names[key]}」上，你的选择与{best["cityName"]}的体验规则较为接近。' for key in strongest]
        dimension_report = [{'key': key, 'name': dimension_names[key], 'score': rounding(value * 100),
                             'preference': f'与{best["cityName"]}的匹配 {rounding(value * 100)}%',
                             'description': '根据该维度各题的选项亲和分归一化计算，仅用于娱乐与自我观察。'}
                            for key, value in best['_dimensions'].items()]
        candidates = [{key: value for key, value in city.items() if not key.startswith('_')} for city in ranked]
        CityResult.objects.get_or_create(attempt=attempt, defaults={'best_match_city': best['cityName'],
            'best_match_code': best['cityCode'], 'match_index': best['score'], 'match_reasons': reasons,
            'top_candidates': candidates[:5], 'dimensions': dimension_report,
            'details': {**metadata(attempt), 'allCandidates': candidates}})
    elif rule.get('algorithm') == 'linear_entertainment_age':
        scores = {(row['question_id'], option): value for row in rule['option_scores'] for option, value in row['scores'].items()}
        try:
            total = sum(scores[(a.question.question_id, a.option.option_id)] for a in answers)
        except KeyError:
            raise ValidationError('评分规则不完整')
        count = len(answers)
        age = rounding(rule['minimum_age'] + ((total - count) / (count * 4)) * (rule['maximum_age'] - rule['minimum_age']))
        age = max(rule['minimum_age'], min(rule['maximum_age'], age))
        category = next(item for item in rule['types'] if item['age_min'] <= age <= item['age_max'])
        template = attempt.version.report_template[category['label']]
        MentalAgeResult.objects.get_or_create(attempt=attempt, defaults={'mental_age': age,
            'type_name': category['label'], 'type_description': template['description'],
            'insights': [template['quote'], *[f'选择倾向：{trait}' for trait in template['traits']]],
            'details': {**metadata(attempt), 'totalScore': total, 'answerDistribution': dict(Counter(a.option.option_id for a in answers))}})
    else:
        raise ValidationError('该版本评分规则不可用')
    attempt.result_generated = True
    attempt.save(update_fields=['result_generated', 'updated_at'])


@transaction.atomic
def generate_result(attempt_id):
    attempt = QuizAttempt.objects.select_for_update(of=('self',)).select_related('version', 'grant__access_code__order').get(pk=attempt_id)
    generate_locked(attempt)
