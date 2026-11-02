from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from ledger.models import Transaction


def shift_month(value, offset):
    index = value.year * 12 + value.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def month_bounds(value):
    first = value.replace(day=1)
    last = value.replace(day=monthrange(value.year, value.month)[1])
    return first, last


def spending_snapshot(owner, today=None):
    today = today or timezone.localdate()
    current_start, current_end = month_bounds(today)
    base = Transaction.objects.filter(owner=owner)
    current = base.filter(transaction_date__range=(current_start, current_end))
    expense = current.filter(flow=Transaction.Flow.EXPENSE).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    income = current.filter(flow=Transaction.Flow.INCOME).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    categories = list(
        current.filter(flow=Transaction.Flow.EXPENSE)
        .values("category").annotate(total=Sum("amount")).order_by("-total")[:6]
    )

    first_month = shift_month(today.replace(day=1), -5)
    monthly_data = base.filter(transaction_date__gte=first_month).annotate(month=TruncMonth("transaction_date"))
    totals = {
        row["month"].date().replace(day=1): row["total"]
        for row in monthly_data.filter(flow=Transaction.Flow.EXPENSE).values("month").annotate(total=Sum("amount"))
    }
    months = []
    for offset in range(-5, 1):
        month = shift_month(today.replace(day=1), offset)
        months.append({"date": month, "label": month.strftime("%b"), "expense": totals.get(month, Decimal("0.00"))})
    peak = max((item["expense"] for item in months), default=Decimal("0.00"))
    for item in months:
        item["bar_height"] = int(item["expense"] / peak * 100) if peak else 0

    complete_months = [shift_month(today.replace(day=1), offset) for offset in (-3, -2, -1)]
    estimate_values = [totals.get(month) for month in complete_months]
    estimate = sum(estimate_values, Decimal("0.00")) / Decimal("3") if all(v is not None for v in estimate_values) else None
    # A zero-expense month is a real observation, not missing data.
    if estimate is not None:
        estimate = estimate.quantize(Decimal("0.01"))

    recent = base[:7]
    return {
        "today": today,
        "current_expense": expense,
        "current_income": income,
        "categories": categories,
        "months": months,
        "estimate": estimate,
        "recent_transactions": recent,
        "transaction_count": base.count(),
    }
