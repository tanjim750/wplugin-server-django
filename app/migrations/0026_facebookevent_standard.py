# Generated by Django 5.2 on 2025-07-14 17:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0025_facebookeventrequest_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='facebookevent',
            name='standard',
            field=models.BooleanField(default=False),
        ),
    ]
