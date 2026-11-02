from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting review"
        IMPORTED = "imported", "Imported"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="import_batches")
    filename = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    added_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} ({self.get_status_display()})"


class StagedTransaction(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="staged_transactions")
    row_number = models.PositiveIntegerField()
    transaction_date = models.DateField()
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    flow = models.CharField(max_length=8, choices=(("expense", "Expense"), ("income", "Income"), ("transfer", "Transfer")))
    category = models.CharField(max_length=80, default="Uncategorized")
    account = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["row_number"]


class Transaction(models.Model):
    class Flow(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"
        TRANSFER = "transfer", "Transfer"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    transaction_date = models.DateField(db_index=True)
    description = models.CharField(max_length=240)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    flow = models.CharField(max_length=8, choices=Flow.choices)
    category = models.CharField(max_length=80, default="Uncategorized", db_index=True)
    account = models.CharField(max_length=100, blank=True)
    fingerprint = models.CharField(max_length=64)
    source_import = models.ForeignKey(ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "fingerprint"], name="unique_owner_transaction_fingerprint"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="transaction_amount_nonnegative"),
        ]
        indexes = [models.Index(fields=["owner", "transaction_date"], name="ledger_owner_date_idx")]

    def __str__(self):
        return f"{self.description} · {self.amount}"
