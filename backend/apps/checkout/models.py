from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid
import secrets


def generate_order_id():
    """生成订单ID"""
    return uuid.uuid4().hex


class Order(models.Model):
    """订单"""

    STATUS_CHOICES = [
        ('pending', '待支付'),
        ('paid', '已支付'),
        ('testing', '测试授权'),
        ('expired', '已过期'),
        ('refunded', '已退款'),
    ]

    id = models.CharField(
        max_length=32,
        primary_key=True,
        default=generate_order_id,
        editable=False,
        verbose_name='订单ID'
    )

    product = models.ForeignKey(
        'catalog.QuizProduct',
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='商品'
    )

    owner_token = models.CharField(max_length=64, blank=True, default='', db_index=True)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True)
    version = models.ForeignKey('catalog.QuizVersion', on_delete=models.PROTECT, null=True, blank=True)
    product_title = models.CharField(max_length=100, blank=True, default='')
    is_test = models.BooleanField(default=False)
    refund_state = models.CharField(max_length=16, default='none', choices=[('none', '未退款'), ('pending', '退款处理中'), ('success', '已退款'), ('failed', '退款失败')])
    manual_reference = models.CharField(max_length=120, blank=True, default='')
    refund_reference = models.CharField(max_length=120, blank=True, default='')

    # 订单金额（分）
    amount = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='订单金额(分)'
    )
    currency = models.CharField(max_length=3, default='CNY', verbose_name='货币')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='订单状态',
        db_index=True
    )

    # 来源追踪（用于渠道分析）
    source = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='来源'
    )

    # 用户标识（匿名，用于防刷单）
    fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='用户指纹',
        db_index=True
    )

    # 过期时间
    expires_at = models.DateTimeField(verbose_name='过期时间')

    # 支付时间
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='支付时间')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'orders'
        verbose_name = '订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['owner_token', 'idempotency_key'], name='unique_order_idempotency'),
            models.UniqueConstraint(fields=['manual_reference'],
                condition=models.Q(is_test=False, status__in=('paid', 'refunded')) & ~models.Q(manual_reference=''),
                name='unique_confirmed_manual_receipt'),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f'Order {self.id} - {self.status}'

    def is_expired(self):
        """检查订单是否过期"""
        return self.status == 'pending' and timezone.now() > self.expires_at

    def can_claim_access_code(self):
        """是否可以领取密码"""
        return self.status in ('paid', 'testing') and self.refund_state not in ('pending', 'success')

    def mark_as_paid(self):
        """标记为已支付"""
        if self.status in ('pending', 'expired'):
            self.status = 'paid'
            self.paid_at = timezone.now()
            self.save(update_fields=['status', 'paid_at', 'updated_at'])

    def mark_as_expired(self):
        """Conditional update prevents a stale read from overwriting confirmed payment."""
        if self.status == 'pending' and self.is_expired():
            Order.objects.filter(pk=self.pk, status='pending', expires_at__lt=timezone.now()).update(
                status='expired', updated_at=timezone.now())
            self.refresh_from_db()
