from django.db import models
from django.utils import timezone
import uuid


class QuizAttempt(models.Model):
    """答卷"""

    STATUS_CHOICES = [
        ('in_progress', '进行中'),
        ('submitted', '已提交'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='答卷ID'
    )

    grant = models.OneToOneField(
        'access.QuizGrant',
        on_delete=models.PROTECT,
        related_name='attempts',
        verbose_name='答题授权'
    )

    product = models.ForeignKey(
        'catalog.QuizProduct',
        on_delete=models.PROTECT,
        related_name='attempts',
        verbose_name='商品'
    )

    version = models.ForeignKey(
        'catalog.QuizVersion',
        on_delete=models.PROTECT,
        related_name='attempts',
        verbose_name='题库版本'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='in_progress',
        verbose_name='状态',
        db_index=True
    )

    revision = models.PositiveIntegerField(default=0)

    # 当前进度（题号）
    current_question = models.IntegerField(default=1, verbose_name='当前题号')

    # 提交时间
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name='提交时间')

    # 结果是否已生成
    result_generated = models.BooleanField(default=False, verbose_name='结果已生成')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'quiz_attempts'
        verbose_name = '答卷'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Attempt {self.id} - {self.status}'

    def submit(self):
        """提交答卷"""
        if self.status == 'in_progress':
            self.status = 'submitted'
            self.submitted_at = timezone.now()
            self.save(update_fields=['status', 'submitted_at', 'updated_at'])

            # 标记密码为已使用
            self.grant.access_code.mark_as_used()


class Answer(models.Model):
    """答案记录"""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='答卷'
    )

    question = models.ForeignKey(
        'catalog.Question',
        on_delete=models.PROTECT,
        related_name='answers',
        verbose_name='题目'
    )

    option = models.ForeignKey(
        'catalog.QuestionOption',
        on_delete=models.PROTECT,
        related_name='selected_answers',
        verbose_name='选项'
    )

    saved_at = models.DateTimeField(auto_now=True, verbose_name='保存时间')

    class Meta:
        db_table = 'answers'
        verbose_name = '答案'
        verbose_name_plural = verbose_name
        unique_together = [('attempt', 'question')]
        indexes = [
            models.Index(fields=['attempt', 'saved_at']),
        ]

    def __str__(self):
        return f'Answer {self.attempt.id} - Q{self.question.sequence}'


class CityResult(models.Model):
    """城市测评结果"""

    attempt = models.OneToOneField(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='city_result',
        verbose_name='答卷'
    )

    # 最佳匹配城市
    best_match_city = models.CharField(max_length=50, verbose_name='最佳匹配城市')
    best_match_code = models.CharField(max_length=20, verbose_name='城市代码')
    match_index = models.IntegerField(verbose_name='匹配指数')

    # 匹配原因
    match_reasons = models.JSONField(default=list, verbose_name='匹配原因')

    # 候选城市
    top_candidates = models.JSONField(default=list, verbose_name='候选城市')

    # 维度分析
    dimensions = models.JSONField(default=list, verbose_name='维度分析')

    details = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')

    class Meta:
        db_table = 'city_results'
        verbose_name = '城市测评结果'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'CityResult {self.attempt.id} - {self.best_match_city}'


class MentalAgeResult(models.Model):
    """心理年龄结果"""

    attempt = models.OneToOneField(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='mental_result',
        verbose_name='答卷'
    )

    # 心理年龄
    mental_age = models.IntegerField(verbose_name='心理年龄')

    # 类型名称
    type_name = models.CharField(max_length=100, verbose_name='类型名称')
    type_description = models.TextField(verbose_name='类型描述')

    # 洞察
    insights = models.JSONField(default=list, verbose_name='洞察')

    details = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name='生成时间')

    class Meta:
        db_table = 'mental_age_results'
        verbose_name = '心理年龄结果'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'MentalAgeResult {self.attempt.id} - {self.mental_age}岁'
