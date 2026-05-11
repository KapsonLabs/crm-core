from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('suppliers', '0004_alter_localpurchaseorderitem_constraints'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='localpurchaseorderitem',
            name='suppliers_lpo_line_number_uniq_active',
        ),
        migrations.RemoveField(
            model_name='localpurchaseorderitem',
            name='line_number',
        ),
    ]
