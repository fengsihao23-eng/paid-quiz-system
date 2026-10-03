from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    order = models.ForeignKey('checkout.Order', null=True, blank=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=64)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ContinueTicket(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    order = models.ForeignKey('checkout.Order', on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
