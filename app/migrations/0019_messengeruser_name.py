# Generated by Django 5.2 on 2025-07-01 12:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_remove_messengeruser_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='messengeruser',
            name='name',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
