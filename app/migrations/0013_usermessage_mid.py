# Generated by Django 5.2 on 2025-06-27 18:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0012_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usermessage',
            name='mid',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
