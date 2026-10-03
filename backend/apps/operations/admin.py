from django.contrib import admin, messages
from django.utils.html import format_html
from rest_framework.exceptions import ValidationError
from apps.catalog.models import QuizProduct, QuizVersion, Question, QuestionOption, ScoringRule
from apps.checkout.models import Order
from apps.access.models import AccessCode, QuizGrant
from apps.quiz.models import QuizAttempt, Answer, CityResult, MentalAgeResult
from apps.payments.models import Payment, PaymentEvent
from .models import AuditEvent, ContinueTicket
from .services import confirm_manual_payment, record_manual_refund, resend_code

admin.site.site_header = '测评运营后台'
admin.site.site_title = '测评管理'
admin.site.index_title = '订单、测评与审计'


class ReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields if field.name not in self.exclude]

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    exclude = ()


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ('id', 'product_title', 'amount', 'status', 'is_test', 'refund_state', 'created_at')
    list_filter = ('is_test', 'status', 'refund_state', 'product')
    search_fields = ('id', 'manual_reference', 'refund_reference')
    exclude = ('owner_token', 'fingerprint', 'idempotency_key')
    actions = ('confirm_receipt', 'register_completed_refund', 'reissue')

    def get_readonly_fields(self, request, obj=None):
        return [field for field in super().get_readonly_fields(request, obj)
                if field not in ('manual_reference', 'refund_reference')]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(actor=request.user, order=obj, action='receipt_reference_updated',
                                  details={'fields': form.changed_data})

    @admin.action(description='核对凭证后：确认真实收款并发放权限')
    def confirm_receipt(self, request, queryset):
        for order in queryset:
            try:
                confirm_manual_payment(order, request.user)
                self.message_user(request, f'{order.pk} 已确认收款。', messages.SUCCESS)
            except ValidationError as error:
                self.message_user(request, f'{order.pk}: {error.detail}', messages.ERROR)

    @admin.action(description='已在微信完成退款后：登记凭证并撤销权限')
    def register_completed_refund(self, request, queryset):
        for order in queryset:
            try:
                record_manual_refund(order, request.user)
                self.message_user(request, f'{order.pk} 已登记人工退款。', messages.SUCCESS)
            except ValidationError as error:
                self.message_user(request, f'{order.pk}: {error.detail}', messages.ERROR)

    @admin.action(description='重发密码并生成一次性恢复链接（仅选一单）')
    def reissue(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '请只选择一张订单。', messages.ERROR)
            return
        try:
            ticket = resend_code(queryset.get(), request.user, request)
            self.message_user(request, format_html(
                '旧密码和旧会话已失效。恢复链接仅可使用一次，5分钟有效：<a href="{}">{}</a>',
                ticket['url'], ticket['url']), messages.SUCCESS)
        except ValidationError as error:
            self.message_user(request, str(error.detail), messages.ERROR)


@admin.register(QuizProduct)
class ProductAdmin(ReadOnlyAdmin):
    list_display = ('title', 'slug', 'question_count', 'price', 'status', 'current_version')
    def get_readonly_fields(self, request, obj=None):
        return [f for f in super().get_readonly_fields(request, obj) if f not in ('status', 'current_version')]
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'current_version':
            object_id = request.resolver_match.kwargs.get('object_id')
            kwargs['queryset'] = QuizVersion.objects.filter(product_id=object_id, is_published=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if obj.current_version and (obj.current_version.product_id != obj.pk or not obj.current_version.is_published):
            raise ValidationError('只能选择本商品已发布的题库版本')
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(actor=request.user, action='product_publication_updated',
                                  details={'product': obj.slug, 'fields': form.changed_data})


@admin.register(QuizVersion)
class VersionAdmin(ReadOnlyAdmin):
    list_display = ('product', 'version_code', 'is_published', 'approval_state', 'published_at')
    list_filter = ('product', 'approval_state')
    actions = ('approve_content',)

    @admin.action(description='完成题库、评分及报告审核后：批准该版本正式收费')
    def approve_content(self, request, queryset):
        from apps.catalog.management.commands.init_data import validate_content
        for version in queryset:
            try:
                if not version.is_published or version.scoring_rules.count() != 1:
                    raise ValidationError('须先发布完整版本')
                questions = {'questions': [
                    {'id': q.question_id, 'dimension': q.dimension_key,
                     'options': [{'id': option.option_id} for option in q.options.all()]}
                    for q in version.questions.prefetch_related('options')]}
                validate_content(questions, version.scoring_rules.get().rule_data,
                                 45 if version.product.slug == 'city-quiz' else 30)
                version.approval_state = 'approved'
                version.save(update_fields=['approval_state'])
                AuditEvent.objects.create(actor=request.user, action='content_approved',
                                          details={'versionId': version.pk, 'scoringHash': version.scoring_hash})
                self.message_user(request, f'{version} 已批准。', messages.SUCCESS)
            except Exception as error:
                self.message_user(request, f'{version}: {error}', messages.ERROR)


@admin.register(AccessCode)
class CodeAdmin(ReadOnlyAdmin):
    list_display = ('id', 'order', 'product', 'version', 'generation', 'is_activated', 'is_used', 'is_disabled')
    list_filter = ('is_disabled', 'product')
    search_fields = ('order__id',)
    exclude = ('code', 'code_hash', 'encrypted_code')


@admin.register(QuizAttempt)
class AttemptAdmin(ReadOnlyAdmin):
    list_display = ('id', 'product', 'status', 'revision', 'result_generated', 'created_at')
    list_filter = ('product', 'status')
    search_fields = ('id',)


@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ('created_at', 'actor', 'order', 'action')
    list_filter = ('action',)
    search_fields = ('order__id',)


class TicketAdmin(ReadOnlyAdmin):
    exclude = ('token_hash',)


for model in (Question, QuestionOption, ScoringRule, QuizGrant, Answer, CityResult, MentalAgeResult, Payment, PaymentEvent):
    admin.site.register(model, ReadOnlyAdmin)
admin.site.register(ContinueTicket, TicketAdmin)
