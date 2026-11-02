import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


HEADER_ALIASES = {
    "date": ("date", "transactiondate", "posteddate"),
    "description": ("description", "merchant", "payee", "name", "details"),
    "amount": ("amount", "transactionamount", "value"),
    "flow": ("transactiontype", "type", "debitcredit", "direction"),
    "category": ("category", "classification"),
    "account": ("account", "accountname", "accountnumber"),
}
EXPENSE_WORDS = {"debit", "expense", "withdrawal", "withdraw", "payment", "purchase"}
INCOME_WORDS = {"credit", "income", "deposit", "refund", "salary"}
TRANSFER_WORDS = {"transfer", "xfer", "cardpayment", "creditcardpayment", "internaltransfer"}
DATE_FORMATS = ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y")


def _key(value):
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def _mapped_headers(headers):
    normalized = {_key(header): header for header in headers if header}
    result = {}
    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[field] = normalized[alias]
                break
    required = {"date", "description", "amount"}
    missing = required - result.keys()
    if missing:
        raise ValueError("Could not find these required columns: " + ", ".join(sorted(missing)))
    return result


def _parse_date(value):
    text = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("date is not recognized") from exc


def _parse_amount(value):
    text = (value or "").strip().replace(",", "").replace("₹", "").replace("$", "").replace("£", "").replace("€", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        amount = Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount is not a valid number") from exc
    if not amount.is_finite() or amount == 0:
        raise ValueError("amount must be a non-zero number")
    if abs(amount) > Decimal("9999999999.99"):
        raise ValueError("amount is above the supported limit")
    return amount


def parse_csv(uploaded_file):
    raw = b"".join(uploaded_file.chunks())
    if not raw.strip():
        raise ValueError("The CSV file is empty.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ValueError("The file encoding could not be read. Save it as UTF-8 CSV and try again.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError("The file needs a header row.")
    columns = _mapped_headers(reader.fieldnames)
    good_rows, errors = [], []
    total_rows = 0
    for row_number, row in enumerate(reader, start=2):
        if not row or not any((value or "").strip() for value in row.values() if isinstance(value, str)):
            continue
        total_rows += 1
        if total_rows > 25000:
            raise ValueError("This import has more than 25,000 rows. Split it into smaller CSV files.")
        try:
            txn_date = _parse_date(row.get(columns["date"]))
            description = (row.get(columns["description"]) or "").strip()
            if not description:
                raise ValueError("description is blank")
            if len(description) > 240:
                raise ValueError("description is longer than 240 characters")
            amount = _parse_amount(row.get(columns["amount"]))
            category = (row.get(columns.get("category", "")) or "").strip() or "Uncategorized"
            raw_flow = (row.get(columns.get("flow", "")) or "").strip().lower()
            if _key(category) in TRANSFER_WORDS or _key(raw_flow) in TRANSFER_WORDS:
                flow = "transfer"
            elif raw_flow in EXPENSE_WORDS:
                flow = "expense"
            elif raw_flow in INCOME_WORDS:
                flow = "income"
            elif not raw_flow:
                flow = "expense" if amount < 0 else "income"
            else:
                raise ValueError("type must identify income or expense")
            account = (row.get(columns.get("account", "")) or "").strip()
            if len(category) > 80 or len(account) > 100:
                raise ValueError("category or account name is too long")
            good_rows.append({
                "row_number": row_number,
                "transaction_date": txn_date,
                "description": description,
                "amount": abs(amount),
                "flow": flow,
                "category": category,
                "account": account,
            })
        except (ValueError, TypeError) as exc:
            if len(errors) < 100:
                errors.append({"row": row_number, "message": str(exc)})
    return total_rows, good_rows, errors


def fingerprint_key(row):
    return (
        row["transaction_date"].isoformat(), row["description"].strip().casefold(),
        format(Decimal(row["amount"]).quantize(Decimal("0.01")), ".2f"), row["flow"],
        row["category"].strip().casefold(), row["account"].strip().casefold(),
    )


def fingerprint(owner_id, row, occurrence=1):
    parts = (
        str(owner_id), *fingerprint_key(row), str(occurrence),
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
