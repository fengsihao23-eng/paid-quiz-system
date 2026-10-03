import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = '仅在首次运行时使用环境变量创建管理账号，不输出或覆盖密码'
    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USERNAME', '')
        password = os.getenv('ADMIN_PASSWORD', '')
        if not username or len(password) < 16:
            raise CommandError('请设置 ADMIN_USERNAME 和至少16位的 ADMIN_PASSWORD')
        user = get_user_model()
        if not user.objects.filter(username=username).exists():
            user.objects.create_superuser(username=username, password=password, email='')
            self.stdout.write('本机管理账号已创建')
        else:
            self.stdout.write('本机管理账号已存在，未修改密码')
