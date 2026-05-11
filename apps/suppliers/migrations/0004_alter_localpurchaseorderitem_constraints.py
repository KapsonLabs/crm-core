# Generated manually for partial unique on active LPO lines only.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0003_localpurchaseorderitem_deleted_status_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='localpurchaseorderitem',
            name='suppliers_lpo_line_number_uniq',
        ),
        migrations.AddConstraint(
            model_name='localpurchaseorderitem',
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_status=False),
                fields=('lpo', 'line_number'),
                name='suppliers_lpo_line_number_uniq_active',
            ),
        ),
    ]
