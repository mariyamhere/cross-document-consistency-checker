
import re
from dataclasses import dataclass
from typing import Optional

import pdfplumber

CANDIDATE_LABELS = [
    ("Net Sales", r"Net Sales\s+(?:PKR\s*)?(\(?[\d,]+\)?)"),
    ("Gross Receipts / Turnover", r"Gross Receipts\s*/\s*Turnover[^\n]*?(?:PKR\s*)?([\d,]+)"),
    ("Gross Receipts", r"Gross Receipts\s+(?:PKR\s*)?([\d,]+)"),
    ("Total Revenue", r"Total Revenue\s+(?:PKR\s*)?([\d,]+)"),
    ("Declared Revenue", r"Declared Revenue\s+(?:PKR\s*)?([\d,]+)"),
    ("Total Income", r"Total Income\s+(?:PKR\s*)?([\d,]+)"),
    ("Declared Income", r"Declared Income\s+(?:PKR\s*)?([\d,]+)"),
    ("Annual Salary / Gross Income", r"Gross (?:Annual )?(?:Salary|Income)\s+(?:PKR\s*)?([\d,]+)"),
    ("Turnover", r"\bTurnover\s+(?:PKR\s*)?([\d,]+)"),
]


@dataclass
class IncomeExtraction:
    matched_label: Optional[str] = None
    amount: Optional[float] = None
    source_text_snippet: Optional[str] = None
    all_candidates: list = None

def extract_declared_income(pdf_path: str) -> IncomeExtraction:
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    candidates = []
    for label, pattern in CANDIDATE_LABELS:
        m = re.search(pattern, full_text)
        if m:
            raw = m.group(1).replace(",", "").replace("(", "-").replace(")", "")
            try:
                amount = float(raw)
            except ValueError:
                continue
            candidates.append({
                "label": label,
                "amount": amount,
                "snippet": m.group(0).strip(),
            })

    if not candidates:
        return IncomeExtraction(all_candidates=[])

    best = candidates[0]
    return IncomeExtraction(
        matched_label=best["label"],
        amount=best["amount"],
        source_text_snippet=best["snippet"],
        all_candidates=candidates,
    )
