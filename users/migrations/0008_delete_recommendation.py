# Generated by Django 5.0 on 2024-09-02 14:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_recommendation'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Recommendation',
        ),
    ]