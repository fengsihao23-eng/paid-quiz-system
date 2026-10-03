from django.db import models
from django.utils import timezone
import secrets
import hashlib


class AccessCode(models.Model):
    """专属密码"""

    order = models.OneToOneField(
        'checkout.Order',
        on_delete=models.PROTECT,
        related_name='access_code',
        verbose_name='订单'
    )

    product = models.ForeignKey(
        'catalog.QuizProduct',
        on_delete=models.PROTECT,
        related_name='access_codes',
        verbose_name='商品'
    )

    version = models.ForeignKey(
        'catalog.QuizVersion',
        on_delete=models.PROTECT,
        related_name='access_codes',
        verbose_name='题库版本'
    )

    # 密码原文（加密存储）
    code = models.CharField(max_length=32, unique=True, null=True, blank=True, verbose_name='旧明文码（迁移后清空）')
    encrypted_code = models.TextField(blank=True, default='')
    generation = models.PositiveIntegerField(default=1)

    # 密码哈希（用于快速查询）
    code_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name='密码哈希'
    )

    # 是否已激活（首次使用）
    is_activated = models.BooleanField(default=False, verbose_name='是否已激活')
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name='激活时间')

    # 是否已使用（提交答卷）
    is_used = models.BooleanField(default=False, verbose_name='是否已使用')
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='使用时间')

    # 是否已禁用（退款等情况）
    is_disabled = models.BooleanField(default=False, verbose_name='是否已禁用')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'access_codes'
        verbose_name = '专属密码'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_activated', 'is_used']),
        ]

    def __str__(self):
        return f'AccessCode {self.id} - {self.product.slug}'

    @staticmethod
    def generate_code():
        """生成16位随机密码"""
        alphabet = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
        raw = ''.join(secrets.choice(alphabet) for _ in range(16))
        return '-'.join(raw[i:i+4] for i in range(0, 16, 4))

    @staticmethod
    def hash_code(code):
        """计算密码哈希"""
        from .crypto import lookup_hash
        return lookup_hash(code)

    def activate(self):
        """激活密码"""
        if not self.is_activated:
            self.is_activated = True
            self.activated_at = timezone.now()
            self.save(update_fields=['is_activated', 'activated_at', 'updated_at'])

    def mark_as_used(self):
        """标记为已使用"""
        if not self.is_used:
            self.is_used = True
            self.used_at = timezone.now()
            self.save(update_fields=['is_used', 'used_at', 'updated_at'])

    def disable(self):
        """禁用密码"""
        self.is_disabled = True
        self.save(update_fields=['is_disabled', 'updated_at'])


class QuizGrant(models.Model):
    """答题授权"""

    access_code = models.OneToOneField(
        AccessCode,
        on_delete=models.PROTECT,
        related_name='grant',
        verbose_name='密码'
    )

    product = models.ForeignKey(
        'catalog.QuizProduct',
        on_delete=models.PROTECT,
        related_name='grants',
        verbose_name='商品'
    )

    version = models.ForeignKey(
        'catalog.QuizVersion',
        on_delete=models.PROTECT,
        related_name='grants',
        verbose_name='题库版本'
    )

    # 当前答卷
    current_attempt = models.ForeignKey(
        'quiz.QuizAttempt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='as_current',
        verbose_name='当前答卷'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'quiz_grants'
        verbose_name = '答题授权'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'Grant {self.id} - {self.product.slug}'

    def get_attempt_status(self):
        """获取答卷状态"""
        if not self.current_attempt:
            return 'not_started'
        return self.current_attempt.status
