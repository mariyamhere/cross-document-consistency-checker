import os
from dataclasses import dataclass
from typing import Optional

import requests

DEFAULT_LOCAL_MODEL = "local-model"

SYSTEM_PROMPT = (
    "You are a credit risk assistant helping a bank analyst interpret a document "
    "reconciliation result. You are given figures and a tier that are already final. "
    "Do not recalculate or dispute them. Respond in under 100 words. List two or three "
    "plausible, non accusatory reasons the gap could exist, then one question the "
    "analyst could ask the applicant to clarify it. Do not assert wrongdoing. "
    "Be brief and specific. No preamble, no repeating the numbers back at length."
)


@dataclass
class ExplanationResult:
    available: bool
    text: Optional[str] = None
    reason_unavailable: Optional[str] = None
    model_used: Optional[str] = None


def _build_user_message(declared_income: float, bank_total_credits: float, gap_pct: float, tier: str) -> str:
    return (
        f"Declared income: PKR {declared_income:,.0f}\n"
        f"Bank credits over the same period: PKR {bank_total_credits:,.0f}\n"
        f"Gap: {gap_pct:.1f} percent lower than declared\n"
        f"Flag tier: {tier}"
    )


def explain_discrepancy(
    declared_income: float,
    bank_total_credits: float,
    gap_pct: float,
    tier: str,
    local_base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: int = 30,
) -> ExplanationResult:
    local_base_url = local_base_url or os.environ.get("LLM_BASE_URL")

    if not local_base_url:
        return ExplanationResult(
            available=False,
            reason_unavailable="No local LLM is connected. Set a Local LLM URL in the sidebar, "
                                "for example an Ollama or LM Studio endpoint.",
        )

    model = model or os.environ.get("LLM_MODEL", DEFAULT_LOCAL_MODEL)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(declared_income, bank_total_credits, gap_pct, tier)},
    ]

    try:
        resp = requests.post(
            local_base_url,
            headers={"Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 250,
                "temperature": 0.4,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        return ExplanationResult(available=True, text=text, model_used=model)
    except requests.exceptions.RequestException as e:
        return ExplanationResult(
            available=False,
            reason_unavailable=f"Request to the local LLM failed: {e}",
        )
    except (KeyError, IndexError, ValueError) as e:
        return ExplanationResult(
            available=False,
            reason_unavailable=f"Unexpected response shape from the local LLM: {e}",
        )
