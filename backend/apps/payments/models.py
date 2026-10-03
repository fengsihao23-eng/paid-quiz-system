from django.db import models
from django.core.validators import MinValueValidator


class Payment(models.Model):
    """支付记录"""

    PROVIDER_CHOICES = [
        ('wechat', '微信支付'),
    ]

    STATUS_CHOICES = [
        ('pending', '待支付'),
        ('processing', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('refunded', '已退款'),
    ]

    METHOD_CHOICES = [
        ('native', 'Native扫码'),
        ('h5', 'H5支付'),
        ('jsapi', 'JSAPI'),
    ]

    order = models.ForeignKey(
        'checkout.Order',
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name='订单'
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='wechat',
        verbose_name='支付提供商'
    )

    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        verbose_name='支付方式'
    )

    # 金额（分）
    amount = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='支付金额(分)'
    )

    currency = models.CharField(max_length=3, default='CNY', verbose_name='货币')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='支付状态',
        db_index=True
    )

    # 第三方支付交易号
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name='交易号',
        db_index=True
    )

    # 微信返回的预支付ID
    prepay_id = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name='预支付ID'
    )

    # Native支付的二维码链接
    code_url = models.TextField(blank=True, default='', verbose_name='二维码URL')

    # H5支付的跳转链接
    mweb_url = models.TextField(blank=True, default='', verbose_name='H5跳转URL')

    # 支付完成时间
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='支付完成时间')

    # 第三方回调数据
    callback_data = models.JSONField(default=dict, verbose_name='回调数据')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'payments'
        constraints = [models.UniqueConstraint(fields=['order', 'provider', 'method'], name='unique_payment_channel')]
        verbose_name = '支付记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Payment {self.id} - {self.order.id} - {self.status}'

    def mark_as_success(self, transaction_id, paid_at=None):
        """标记支付成功"""
        from django.utils import timezone
        self.status = 'success'
        self.transaction_id = transaction_id
        self.paid_at = paid_at or timezone.now()
        self.save(update_fields=['status', 'transaction_id', 'paid_at', 'updated_at'])

        # 同时更新订单状态
        self.order.mark_as_paid()


class RefundRecord(models.Model):
    """退款记录"""

    STATUS_CHOICES = [
        ('pending', '处理中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name='refunds',
        verbose_name='支付记录'
    )

    # 退款金额（分）
    amount = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='退款金额(分)'
    )

    reason = models.TextField(verbose_name='退款原因')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='退款状态'
    )

    # 第三方退款单号
    refund_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name='退款单号'
    )

    # 退款完成时间
    refunded_at = models.DateTimeField(null=True, blank=True, verbose_name='退款完成时间')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'refund_records'
        verbose_name = '退款记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Refund {self.id} - {self.payment.order.id} - {self.status}'


class PaymentEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    source = models.CharField(max_length=16)
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default='pending')
    error = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
