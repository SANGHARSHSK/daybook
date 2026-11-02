from django.contrib import admin

from .models import ImportBatch, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_date", "description", "owner", "flow", "amount", "category")
    list_filter = ("flow", "category")
    search_fields = ("description", "owner__username", "category")
    date_hierarchy = "transaction_date"


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("filename", "owner", "status", "total_rows", "added_rows", "created_at")
    readonly_fields = ("errors", "created_at", "completed_at")
