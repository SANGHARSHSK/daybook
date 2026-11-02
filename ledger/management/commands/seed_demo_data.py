from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ledger.models import Transaction
from ledger.services.imports import fingerprint
from ledger.services.summaries import shift_month


class Command(BaseCommand):
    help = "Add clearly fictional, recent transactions to an empty reviewer account."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Existing account that will own the sample ledger")

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("Create that account first, then run this command again.") from exc
        if Transaction.objects.filter(owner=user).exists():
            raise CommandError("That account already has transactions. Sample data is only added to an empty ledger.")

        today = timezone.localdate()
        recurring = [
            ("Paycheck", "62000.00", "income", "Salary", "Checking"),
            ("Northside Market", "2480.00", "expense", "Groceries", "Everyday Card"),
            ("Metro monthly pass", "1450.00", "expense", "Transport", "Everyday Card"),
            ("Electric company", "1820.00", "expense", "Utilities", "Checking"),
            ("Neighborhood Cafe", "385.00", "expense", "Dining", "Everyday Card"),
            ("Rent transfer", "18500.00", "expense", "Housing", "Checking"),
            ("Green Basket", "1310.00", "expense", "Groceries", "Everyday Card"),
            ("Bookshop on 4th", "740.00", "expense", "Personal", "Everyday Card"),
            ("Pharmacy", "560.00", "expense", "Health", "Everyday Card"),
            ("Dinner with Maya", "1280.00", "expense", "Dining", "Everyday Card"),
        ]
        created = 0
        for offset in range(-7, 1):
            month = shift_month(today.replace(day=1), offset)
            for index, (description, amount, flow, category, account) in enumerate(recurring):
                txn_date = month.replace(day=min((index * 3 + 2), 26))
                # Small, deterministic shifts make each month's sample feel like a ledger, not a clone.
                multiplier = Decimal("1.00") + Decimal((offset + 8) % 5) / Decimal("100")
                values = {
                    "transaction_date": txn_date,
                    "description": description,
                    "amount": (Decimal(amount) * multiplier).quantize(Decimal("0.01")),
                    "flow": flow,
                    "category": category,
                    "account": account,
                }
                _, was_created = Transaction.objects.get_or_create(
                    owner=user,
                    fingerprint=fingerprint(user.pk, values),
                    defaults=values,
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Added {created} fictional sample transactions to {user.username}."))
