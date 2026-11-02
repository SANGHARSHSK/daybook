import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ImportBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filename", models.CharField(max_length=160)),
                ("status", models.CharField(choices=[("pending", "Awaiting review"), ("imported", "Imported"), ("cancelled", "Cancelled")], default="pending", max_length=12)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("valid_rows", models.PositiveIntegerField(default=0)),
                ("invalid_rows", models.PositiveIntegerField(default=0)),
                ("added_rows", models.PositiveIntegerField(default=0)),
                ("duplicate_rows", models.PositiveIntegerField(default=0)),
                ("errors", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="import_batches", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_date", models.DateField(db_index=True)),
                ("description", models.CharField(max_length=240)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("flow", models.CharField(choices=[("expense", "Expense"), ("income", "Income"), ("transfer", "Transfer")], max_length=8)),
                ("category", models.CharField(db_index=True, default="Uncategorized", max_length=80)),
                ("account", models.CharField(blank=True, max_length=100)),
                ("fingerprint", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transactions", to=settings.AUTH_USER_MODEL)),
                ("source_import", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transactions", to="ledger.importbatch")),
            ],
            options={"ordering": ["-transaction_date", "-id"]},
        ),
        migrations.CreateModel(
            name="StagedTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_number", models.PositiveIntegerField()),
                ("transaction_date", models.DateField()),
                ("description", models.CharField(max_length=240)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("flow", models.CharField(choices=[("expense", "Expense"), ("income", "Income"), ("transfer", "Transfer")], max_length=8)),
                ("category", models.CharField(default="Uncategorized", max_length=80)),
                ("account", models.CharField(blank=True, max_length=100)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staged_transactions", to="ledger.importbatch")),
            ],
            options={"ordering": ["row_number"]},
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.UniqueConstraint(fields=("owner", "fingerprint"), name="unique_owner_transaction_fingerprint"),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.CheckConstraint(condition=models.Q(("amount__gte", 0)), name="transaction_amount_nonnegative"),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(fields=["owner", "transaction_date"], name="ledger_owner_date_idx"),
        ),
    ]
