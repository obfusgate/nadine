# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-30 17:28
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('nadine', '0029_new_bill'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coworkingday',
            name='bill',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='nadine.UserBill'),
        ),
    ]
