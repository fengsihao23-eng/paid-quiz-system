from rest_framework import serializers

class CreateOrderSerializer(serializers.Serializer):
    product_slug = serializers.SlugField()
    source = serializers.CharField(max_length=100, required=False, allow_blank=True)

class OrderSerializer(serializers.BaseSerializer):
    def to_representation(self, order):
        return {'id': order.id, 'productSlug': order.product.slug, 'productTitle': order.product_title or order.product.title,
                'amount': order.amount, 'currency': order.currency, 'status': order.status, 'isTest': order.is_test,
                'createdAt': order.created_at.isoformat(), 'expiresAt': order.expires_at.isoformat(),
                'paidAt': order.paid_at.isoformat() if order.paid_at else None,
                'refundState': order.refund_state, 'contentVersion': order.version.version_code if order.version else ''}
