import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.catalog.models import QuizProduct
from apps.catalog.publication import publish_content


class Command(BaseCommand):
    help = '验证并发布当前两套娱乐测评，记录运营账号和发布原因'

    def add_arguments(self, parser):
        parser.add_argument('--actor', default=os.getenv('ADMIN_USERNAME', 'quizadmin'))
        parser.add_argument('--reason', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options['actor'], is_active=True, is_staff=True).first()
        if not actor:
            raise CommandError('找不到有效的运营账号')
        products = list(QuizProduct.objects.select_for_update(of=('self',)).select_related('current_version')
                        .filter(slug__in=('city-quiz', 'mental-age-quiz')).order_by('slug'))
        if len(products) != 2 or any(not p.current_version or p.status != 'published' for p in products):
            raise CommandError('请先完整导入并发布两套测评')
        for product in products:
            try:
                changed = publish_content(product.current_version, actor, options['reason'])
            except Exception as error:
                raise CommandError(f'{product.slug} 发布失败：{error}') from error
            self.stdout.write(f'{product.title}：' + ('已发布完整娱乐测评' if changed else '已发布，保持现有内容'))
