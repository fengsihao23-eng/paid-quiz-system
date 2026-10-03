from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('checkout', '0003_order_refund_reference')]

    operations = [
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(
                fields=('manual_reference',),
                condition=models.Q(is_test=False, status__in=('paid', 'refunded')) & ~models.Q(manual_reference=''),
                name='unique_confirmed_manual_receipt',
            ),
        ),
    ]
