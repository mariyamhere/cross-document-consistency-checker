
import re
from dataclasses import dataclass, field
from typing import Optional
import pdfplumber

# Matches a line like:
# "04-Jul-2025 Receipt - Customer A (Cheque Clearing) - 12,516,000 16,716,000"
# groups: date, description, debit ('-' or number), credit ('-' or number), balance
TRANSACTION_LINE = re.compile(
    r"^(\d{2}-[A-Za-z]{3}-\d{4})\s+(.+?)\s+(-|[\d,]+)\s+(-|[\d,]+)\s+([\d,]+)$",
    re.MULTILINE,
)

TOTAL_LINE = re.compile(
    r"^TOTAL\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)$",
    re.MULTILINE,
)


def _to_amount(token: str) -> float:
    if token == "-" or token is None:
        return 0.0
    return float(token.replace(",", ""))


@dataclass
class Transaction:
    date: str
    description: str
    debit: float
    credit: float
    balance: float


@dataclass
class BankStatementSummary:
    transactions: list = field(default_factory=list)
    total_credits: Optional[float] = None
    total_debits: Optional[float] = None
    closing_balance: Optional[float] = None
    stated_total_credits: Optional[float] = None  # from the statement's own total row if present
    stated_total_debits: Optional[float] = None
    stated_closing_balance: Optional[float] = None
    extraction_warning: Optional[str] = None


def parse_bank_statement(pdf_path: str) -> BankStatementSummary:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    transactions = []
    for m in TRANSACTION_LINE.finditer(full_text):
        date, desc, debit_tok, credit_tok, balance_tok = m.groups()
        transactions.append(Transaction(
            date=date,
            description=desc.strip(),
            debit=_to_amount(debit_tok),
            credit=_to_amount(credit_tok),
            balance=_to_amount(balance_tok),
        ))

    summary = BankStatementSummary(transactions=transactions)

    if not transactions:
        summary.extraction_warning = (
            "No transaction rows were recognized in this PDF. The parser expects a table "
            "with Date, Description, Debit, Credit and Balance columns, one row per line. "
            "A different statement layout will need its own parser."
        )
        return summary

    summary.total_credits = round(sum(t.credit for t in transactions), 2)
    summary.total_debits = round(sum(t.debit for t in transactions), 2)
    summary.closing_balance = transactions[-1].balance

    # If the statement also prints its own TOTAL row, capture it too so the
    # UI can show "our sum" vs "the bank's own total" as a sanity check.
    total_match = TOTAL_LINE.search(full_text)
    if total_match:
        summary.stated_total_debits = _to_amount(total_match.group(1))
        summary.stated_total_credits = _to_amount(total_match.group(2))
        summary.stated_closing_balance = _to_amount(total_match.group(3))

    return summary
