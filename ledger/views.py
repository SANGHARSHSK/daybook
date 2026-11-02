import csv
from datetime import date, timedelta
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .forms import CSVUploadForm, SignUpForm
from .models import ImportBatch, StagedTransaction, Transaction
from .services.imports import fingerprint, fingerprint_key, parse_csv
from .services.summaries import spending_snapshot


def sign_up(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your Daybook is ready. Start with a transaction import.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form, "invite_required": bool(settings.REGISTRATION_INVITE_CODE)})


@login_required
def dashboard(request):
    data = spending_snapshot(request.user)
    return render(request, "ledger/dashboard.html", data)


@login_required
def transaction_list(request):
    query = request.GET.get("q", "").strip()[:100]
    flow = request.GET.get("flow", "")
    category = request.GET.get("category", "").strip()[:80]
    month = request.GET.get("month", "")
    transactions = Transaction.objects.filter(owner=request.user)
    if query:
        transactions = transactions.filter(description__icontains=query)
    if flow in {Transaction.Flow.EXPENSE, Transaction.Flow.INCOME, Transaction.Flow.TRANSFER}:
        transactions = transactions.filter(flow=flow)
    if category:
        transactions = transactions.filter(category=category)
    if month:
        try:
            month_start = date.fromisoformat(month + "-01")
            next_month = date(month_start.year + (month_start.month == 12), month_start.month % 12 + 1, 1)
            transactions = transactions.filter(transaction_date__gte=month_start, transaction_date__lt=next_month)
        except ValueError:
            month = ""
    categories = Transaction.objects.filter(owner=request.user).values_list("category", flat=True).distinct().order_by("category")
    page = Paginator(transactions, 25).get_page(request.GET.get("page"))
    return render(request, "ledger/transactions.html", {
        "page": page, "query": query, "flow_filter": flow, "category_filter": category,
        "month_filter": month, "categories": categories, "result_count": transactions.count(),
    })


@login_required
def import_upload(request):
    stale = ImportBatch.objects.filter(
        owner=request.user,
        status=ImportBatch.Status.PENDING,
        created_at__lt=timezone.now() - timedelta(hours=24),
    )
    stale_ids = list(stale.values_list("id", flat=True))
    StagedTransaction.objects.filter(batch_id__in=stale_ids).delete()
    stale.update(status=ImportBatch.Status.CANCELLED, completed_at=timezone.now())
    form = CSVUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            total_rows, rows, errors = parse_csv(form.cleaned_data["file"])
        except (ValueError, csv.Error) as exc:
            form.add_error("file", str(exc))
        else:
            if total_rows == 0:
                form.add_error("file", "No transaction rows were found in that file.")
            else:
                batch = ImportBatch.objects.create(
                    owner=request.user,
                    filename=form.cleaned_data["file"].name[:160],
                    total_rows=total_rows,
                    valid_rows=len(rows),
                    invalid_rows=total_rows - len(rows),
                    errors=errors,
                )
                StagedTransaction.objects.bulk_create(
                    [StagedTransaction(batch=batch, **row) for row in rows], batch_size=500
                )
                return redirect("import_review", batch_id=batch.pk)
    return render(request, "ledger/import_upload.html", {"form": form})


@login_required
def import_review(request, batch_id):
    batch = get_object_or_404(ImportBatch, pk=batch_id, owner=request.user)
    if batch.status == ImportBatch.Status.PENDING and batch.created_at < timezone.now() - timedelta(hours=24):
        batch.staged_transactions.all().delete()
        batch.status = ImportBatch.Status.CANCELLED
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at"])
        messages.info(request, "This review expired after 24 hours. Please start a fresh import.")
    if batch.status != ImportBatch.Status.PENDING:
        return redirect("import_result", batch_id=batch.pk)
    preview = batch.staged_transactions.all()[:8]
    return render(request, "ledger/import_review.html", {"batch": batch, "preview": preview, "errors": batch.errors[:12]})


@login_required
@require_POST
def import_confirm(request, batch_id):
    with db_transaction.atomic():
        batch = get_object_or_404(ImportBatch.objects.select_for_update(), pk=batch_id, owner=request.user)
        if batch.status != ImportBatch.Status.PENDING:
            return redirect("import_result", batch_id=batch.pk)
        added = duplicates = 0
        occurrences = {}
        for staged in batch.staged_transactions.all().iterator():
            values = {
                "transaction_date": staged.transaction_date,
                "description": staged.description,
                "amount": staged.amount,
                "flow": staged.flow,
                "category": staged.category,
                "account": staged.account,
            }
            key = fingerprint_key(values)
            occurrences[key] = occurrences.get(key, 0) + 1
            _, created = Transaction.objects.get_or_create(
                owner=request.user,
                fingerprint=fingerprint(request.user.pk, values, occurrences[key]),
                defaults={**values, "source_import": batch},
            )
            added += int(created)
            duplicates += int(not created)
        batch.status = ImportBatch.Status.IMPORTED
        batch.added_rows = added
        batch.duplicate_rows = duplicates
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "added_rows", "duplicate_rows", "completed_at"])
        batch.staged_transactions.all().delete()
    messages.success(request, f"Import complete: {added} added, {duplicates} already in your Daybook.")
    return redirect("import_result", batch_id=batch.pk)


@login_required
@require_POST
def import_cancel(request, batch_id):
    with db_transaction.atomic():
        batch = get_object_or_404(ImportBatch.objects.select_for_update(), pk=batch_id, owner=request.user)
        if batch.status == ImportBatch.Status.PENDING:
            batch.staged_transactions.all().delete()
            batch.status = ImportBatch.Status.CANCELLED
            batch.completed_at = timezone.now()
            batch.save(update_fields=["status", "completed_at"])
    messages.info(request, "That import was discarded.")
    return redirect("transactions")


@login_required
def import_result(request, batch_id):
    batch = get_object_or_404(ImportBatch, pk=batch_id, owner=request.user)
    return render(request, "ledger/import_result.html", {"batch": batch})


@login_required
def export_transactions(request):
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Description", "Amount", "Type", "Category", "Account"])
    for item in Transaction.objects.filter(owner=request.user).iterator():
        cells = [item.transaction_date.isoformat(), item.description, f"{item.amount:.2f}", item.get_flow_display(), item.category, item.account]
        # Spreadsheet programs can interpret user supplied text as a formula.
        cells = [("'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value) for value in cells]
        writer.writerow(cells)
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="daybook-transactions.csv"'
    response["Cache-Control"] = "no-store"
    return response


def health(request):
    return HttpResponse("ok", content_type="text/plain")
