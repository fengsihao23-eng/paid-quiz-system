from django.db import models
from django.core.validators import MinValueValidator
import hashlib
import json


class QuizProduct(models.Model):
    """测评商品"""

    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('published', '已发布'),
        ('archived', '已归档'),
    ]

    slug = models.SlugField(max_length=50, unique=True, verbose_name='商品标识')
    title = models.CharField(max_length=100, verbose_name='商品名称')
    description = models.TextField(verbose_name='商品描述')
    question_count = models.IntegerField(verbose_name='题目数量')
    estimated_minutes = models.CharField(max_length=20, verbose_name='预计用时')

    # 价格以分为单位存储
    price = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='价格(分)'
    )
    currency = models.CharField(max_length=3, default='CNY', verbose_name='货币')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name='状态'
    )

    current_version = models.ForeignKey(
        'QuizVersion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='as_current_version',
        verbose_name='当前版本'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'quiz_products'
        verbose_name = '测评商品'
        verbose_name_plural = verbose_name
        ordering = ['slug']

    def __str__(self):
        return self.title


class QuizVersion(models.Model):
    """题库版本"""

    product = models.ForeignKey(
        QuizProduct,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='所属商品'
    )

    version_code = models.CharField(max_length=50, verbose_name='版本号')

    # 题库数据的JSON或引用
    questions_hash = models.CharField(max_length=64, verbose_name='题库哈希')
    scoring_hash = models.CharField(max_length=64, verbose_name='评分哈希')

    approval_state = models.CharField(max_length=16, default='draft', choices=[('draft', '草稿'), ('preview', '客户体验'), ('approved', '审核通过')])
    content_note = models.TextField(blank=True, default='')
    report_template = models.JSONField(default=dict)
    is_published = models.BooleanField(default=False, verbose_name='是否已发布')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'quiz_versions'
        verbose_name = '题库版本'
        verbose_name_plural = verbose_name
        unique_together = [('product', 'version_code')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.slug}-{self.version_code}'


class Question(models.Model):
    """题目"""

    version = models.ForeignKey(
        QuizVersion,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='所属版本'
    )

    question_id = models.CharField(max_length=50, verbose_name='题目ID')
    sequence = models.IntegerField(verbose_name='题目序号')

    dimension_key = models.CharField(max_length=50, verbose_name='维度键')
    dimension_name = models.CharField(max_length=100, verbose_name='维度名称')

    text = models.TextField(verbose_name='题目文本')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'questions'
        verbose_name = '题目'
        verbose_name_plural = verbose_name
        unique_together = [('version', 'question_id')]
        ordering = ['sequence']

    def __str__(self):
        return f'{self.question_id}: {self.text[:30]}'


class QuestionOption(models.Model):
    """题目选项"""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name='所属题目'
    )

    option_id = models.CharField(max_length=50, verbose_name='选项ID')
    sequence = models.IntegerField(verbose_name='选项序号')
    text = models.TextField(verbose_name='选项文本')

    # 评分权重 - 以JSON存储，不向前端公开
    scoring_data = models.JSONField(default=dict, verbose_name='评分数据')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'question_options'
        verbose_name = '题目选项'
        verbose_name_plural = verbose_name
        unique_together = [('question', 'option_id')]
        ordering = ['sequence']

    def __str__(self):
        return f'{self.option_id}: {self.text[:30]}'


class ScoringRule(models.Model):
    """评分规则"""

    version = models.ForeignKey(
        QuizVersion,
        on_delete=models.CASCADE,
        related_name='scoring_rules',
        verbose_name='所属版本'
    )

    rule_type = models.CharField(max_length=50, verbose_name='规则类型')
    rule_data = models.JSONField(verbose_name='规则数据')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'scoring_rules'
        verbose_name = '评分规则'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.version} - {self.rule_type}'
