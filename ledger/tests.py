from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ImportBatch, Transaction


class LedgerViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="reader", password="Good-password-42")
        self.client.force_login(self.owner)

    def upload(self, content):
        return SimpleUploadedFile("statement.csv", content.encode("utf-8"), content_type="text/csv")

    def statement(self):
        today = timezone.localdate()
        stamp = today.strftime("%m/%d/%Y")
        return (
            "Date,Description,Amount,Transaction Type,Category,Account Name\n"
            f"{stamp},Corner Cafe,5.25,debit,Dining,Everyday Card\n"
            f"{stamp},Corner Cafe,5.25,debit,Dining,Everyday Card\n"
            f"{stamp},Monthly pay,2000.00,credit,Income,Checking\n"
            f"{stamp},Card payment,100.00,debit,Credit Card Payment,Checking\n"
            "not-a-date,Broken row,12.00,debit,Other,Checking\n"
        )

    def test_import_review_confirm_and_reimport_preserve_repeated_transactions(self):
        response = self.client.post(reverse("import_upload"), {"file": self.upload(self.statement())})
        self.assertEqual(response.status_code, 302)
        batch = ImportBatch.objects.get(owner=self.owner)
        self.assertEqual(batch.valid_rows, 4)
        self.assertEqual(batch.invalid_rows, 1)
        self.assertEqual(batch.staged_transactions.count(), 4)

        response = self.client.get(reverse("import_review", args=[batch.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Card payment")
        self.client.post(reverse("import_confirm", args=[batch.pk]))

        transactions = Transaction.objects.filter(owner=self.owner)
        self.assertEqual(transactions.count(), 4)
        self.assertEqual(transactions.filter(flow=Transaction.Flow.EXPENSE).aggregate(total=Sum("amount"))["total"], Decimal("10.50"))
        self.assertEqual(transactions.filter(flow=Transaction.Flow.TRANSFER).count(), 1)
        self.assertEqual(transactions.filter(flow=Transaction.Flow.INCOME).count(), 1)

        response = self.client.post(reverse("import_upload"), {"file": self.upload(self.statement())})
        repeated_batch = ImportBatch.objects.get(owner=self.owner, status=ImportBatch.Status.PENDING)
        self.client.post(reverse("import_confirm", args=[repeated_batch.pk]))
        repeated_batch.refresh_from_db()
        self.assertEqual(repeated_batch.added_rows, 0)
        self.assertEqual(repeated_batch.duplicate_rows, 4)
        self.assertEqual(Transaction.objects.filter(owner=self.owner).count(), 4)

    def test_dashboard_and_transaction_pages_show_only_the_signed_in_users_data(self):
        other = User.objects.create_user(username="someone-else", password="Good-password-42")
        Transaction.objects.create(
            owner=other,
            transaction_date=date(2026, 1, 1),
            description="Private purchase",
            amount=Decimal("800.00"),
            flow=Transaction.Flow.EXPENSE,
            category="Personal",
            fingerprint="b" * 64,
        )

        dashboard = self.client.get(reverse("dashboard"))
        listing = self.client.get(reverse("transactions"))
        export = self.client.get(reverse("export_transactions"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "Private purchase")
        self.assertEqual(listing.context["result_count"], 0)
        self.assertNotIn("Private purchase", export.content.decode())

    def test_import_batch_cannot_be_reviewed_by_a_different_user(self):
        batch = ImportBatch.objects.create(owner=self.owner, filename="private.csv")
        other = User.objects.create_user(username="intruder", password="Good-password-42")
        self.client.force_login(other)
        response = self.client.get(reverse("import_review", args=[batch.pk]))
        self.assertEqual(response.status_code, 404)
