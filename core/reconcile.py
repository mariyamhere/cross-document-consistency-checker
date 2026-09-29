from dataclasses import dataclass
from typing import Optional
NORMAL_GAP_PCT = 12.0        
ELEVATED_MULTIPLIER = 1.5   
@dataclass
class ReconciliationResult:
    tier: str                      
    declared_income: Optional[float]
    bank_total_credits: Optional[float]
    gap_amount: Optional[float]
    gap_pct: Optional[float]
    detail: str


def reconcile(declared_income: Optional[float], bank_total_credits: Optional[float]) -> ReconciliationResult:
    if declared_income is None or bank_total_credits is None:
        return ReconciliationResult(
            tier="UNKNOWN",
            declared_income=declared_income,
            bank_total_credits=bank_total_credits,
            gap_amount=None,
            gap_pct=None,
            detail="Missing one or both figures. Reconciliation cannot run until both are provided.",
        )

    if declared_income <= 0:
        return ReconciliationResult(
            tier="UNKNOWN",
            declared_income=declared_income,
            bank_total_credits=bank_total_credits,
            gap_amount=None,
            gap_pct=None,
            detail="Declared income is zero or negative. A percentage gap cannot be computed.",
        )

    gap_amount = declared_income - bank_total_credits
    gap_pct = (gap_amount / declared_income) * 100

    if bank_total_credits > declared_income:
        # Bank credits exceeding declared income is the unexpected direction,
        # always worth a look regardless of magnitude.
        overshoot_pct = abs(gap_pct)
        return ReconciliationResult(
            tier="DISCREPANCY",
            declared_income=declared_income,
            bank_total_credits=bank_total_credits,
            gap_amount=gap_amount,
            gap_pct=gap_pct,
            detail=(
                f"Bank credits (PKR {bank_total_credits:,.0f}) exceed declared income "
                f"(PKR {declared_income:,.0f}) by {overshoot_pct:.1f}%. This is an unexpected "
                f"direction. Check whether the declared figure is complete, or whether the "
                f"account includes inflows unrelated to revenue such as loans or transfers."
            ),
        )

    if gap_pct <= NORMAL_GAP_PCT:
        tier = "MATCH"
        note = "within the normal range"
    elif gap_pct <= NORMAL_GAP_PCT * ELEVATED_MULTIPLIER:
        tier = "VARIANCE"
        note = "above the normal range but not yet flagged as material"
    else:
        tier = "DISCREPANCY"
        note = "well beyond the normal range and worth investigating"

    detail = (
        f"Declared income is PKR {declared_income:,.0f}. Bank credits are PKR {bank_total_credits:,.0f}, "
        f"which is {gap_pct:.1f}% lower ({note}). Normal range is up to {NORMAL_GAP_PCT:.0f}%."
    )

    return ReconciliationResult(
        tier=tier,
        declared_income=declared_income,
        bank_total_credits=bank_total_credits,
        gap_amount=gap_amount,
        gap_pct=gap_pct,
        detail=detail,
    )
