"""
Document Reconciliation Tool. Streamlit app.

User uploads a bank statement PDF and an income document (or types a
declared income figure directly), and the app deterministically checks
whether bank credits and declared income line up.

Run with:
    streamlit run app.py
"""
import os
import tempfile

import streamlit as st

from core.bank_statement import parse_bank_statement
from core.income_document import extract_declared_income
from core.reconcile import reconcile
from core.llm_explain import explain_discrepancy, DEFAULT_LOCAL_MODEL

st.set_page_config(page_title="Check Consistency in Documents", layout="wide")

TIER_LABEL = {
    "MATCH": ("Match", "green"),
    "VARIANCE": ("Variance", "orange"),
    "DISCREPANCY": ("Discrepancy", "red"),
    "UNKNOWN": ("Unknown", "gray"),
}


def save_upload(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        return tmp.name


st.title("Check Consistency in Documents")
st.caption("Runs offline. Checks whether bank statement credits match a declared income figure.")

with st.sidebar:
    st.header("AI Explanation")
    st.caption("Optional. Suggests reasons for a flagged gap after the calculation runs.")
    st.caption("Connect a local llm to generate explanation.")
    local_llm_url = st.text_input(
        "Local LLM URL", value=os.environ.get("LLM_BASE_URL", ""),
        placeholder="http://localhost:11434/v1/chat/completions",
        help="Any OpenAI compatible chat completions endpoint, for example Ollama or LM Studio.",
    )
    local_llm_model = st.text_input(
        "Local LLM model",
        value=os.environ.get("LLM_MODEL", DEFAULT_LOCAL_MODEL),
        help="Model name as your local server expects it.",
    )

col1, col2 = st.columns(2)

with col1:
    st.subheader("Bank Statement")
    bank_file = st.file_uploader("Transaction level bank statement (PDF)", type=["pdf"], key="bank")

with col2:
    st.subheader("Declared Income")
    income_file = st.file_uploader("Income document (PDF), optional", type=["pdf"], key="income")
    manual_income = st.number_input(
        "Or enter the declared income amount (PKR)",
        min_value=0.0, value=0.0, step=1000000.0, format="%.0f",
    )

st.divider()

# Streamlit reruns the whole script on every widget interaction, including
# the "Generate Explanation" button below. Results are stashed in
# session_state on "Run Reconciliation" so they survive that later rerun
# instead of disappearing because the outer button stopped being True.
if st.button("Run Reconciliation", type="primary"):
    if not bank_file:
        st.error("Upload a bank statement PDF.")
        st.stop()

    bank_path = save_upload(bank_file)
    bank_summary = parse_bank_statement(bank_path)

    if bank_summary.extraction_warning:
        st.error(bank_summary.extraction_warning)
        st.session_state.pop("run_result", None)
        st.stop()

    declared_income = None
    income_source_note = None

    if income_file:
        income_path = save_upload(income_file)
        income_extraction = extract_declared_income(income_path)
        if income_extraction.amount is not None:
            declared_income = income_extraction.amount
            income_source_note = f'Matched label "{income_extraction.matched_label}". Amount PKR {declared_income:,.0f}.'

    income_extraction_failed = bool(income_file) and declared_income is None

    if manual_income > 0:
        declared_income = manual_income
        income_source_note = income_source_note or "Entered manually."

    if declared_income is None:
        st.error("No declared income available. Upload a document with a recognizable income label, or enter an amount manually.")
        st.session_state.pop("run_result", None)
        st.stop()

    result = reconcile(declared_income, bank_summary.total_credits)

    st.session_state["run_result"] = {
        "bank_summary": bank_summary,
        "declared_income": declared_income,
        "income_source_note": income_source_note,
        "income_extraction_failed": income_extraction_failed,
        "result": result,
    }
    st.session_state.pop("explanation", None)

if "run_result" in st.session_state:
    data = st.session_state["run_result"]
    bank_summary = data["bank_summary"]
    declared_income = data["declared_income"]
    result = data["result"]

    st.subheader("Bank Statement Figures")
    b1, b2, b3 = st.columns(3)
    b1.metric("Total Credits", f"PKR {bank_summary.total_credits:,.0f}")
    b2.metric("Total Debits", f"PKR {bank_summary.total_debits:,.0f}")
    b3.metric("Closing Balance", f"PKR {bank_summary.closing_balance:,.0f}")

    if bank_summary.stated_total_credits is not None:
        credits_match = abs(bank_summary.stated_total_credits - bank_summary.total_credits) < 1
        debits_match = abs(bank_summary.stated_total_debits - bank_summary.total_debits) < 1
        if credits_match and debits_match:
            st.success("Computed totals match the statement's own printed total row.")
        else:
            st.warning("Computed totals do not match the statement's own printed total row. Some rows may have been missed.")

    with st.expander(f"View all {len(bank_summary.transactions)} extracted transactions", expanded=True):
        st.dataframe(
            [
                {"Date": t.date, "Description": t.description, "Debit": t.debit, "Credit": t.credit, "Balance": t.balance}
                for t in bank_summary.transactions
            ],
            width="stretch",
        )

    if data["income_extraction_failed"]:
        st.warning("No recognizable income label was found in the uploaded document. Using the manually entered amount instead.")

    st.subheader("Declared Income")
    st.metric("Declared Income Used", f"PKR {declared_income:,.0f}")
    st.caption(data["income_source_note"])

    st.divider()
    st.subheader("Reconciliation Result")

    label, color = TIER_LABEL[result.tier]
    st.markdown(f"### :{color}[{label}]")
    st.write(result.detail)

    if result.gap_pct is not None:
        st.progress(min(abs(result.gap_pct) / 50, 1.0), text=f"Gap: {result.gap_pct:.1f}%")

    st.caption("Computed with fixed thresholds. Same inputs always produce the same result.")

    if result.tier in ("VARIANCE", "DISCREPANCY"):
        st.divider()
        st.subheader("AI Explanation")
        st.caption("Suggests possible reasons for the gap. Does not change the result above.")
        st.caption("Connect a local llm to generate explanation.")

        # The reconciliation inputs are deterministic, so the same case should
        # never trigger a second network call: one call per unique input,
        # cached after that.
        cache_key = (
            round(declared_income, 2), round(bank_summary.total_credits, 2),
            round(result.gap_pct, 2), result.tier,
            local_llm_url or None, local_llm_model or None,
        )
        explanation_cache = st.session_state.setdefault("explanation_cache", {})
        cached = explanation_cache.get(cache_key)

        if cached is not None:
            st.caption("Using a cached result for this exact case. No new request sent.")
            explanation = cached
        else:
            explanation = None
            if st.button("Generate Explanation"):
                with st.spinner("Contacting model"):
                    explanation = explain_discrepancy(
                        declared_income=declared_income,
                        bank_total_credits=bank_summary.total_credits,
                        gap_pct=result.gap_pct,
                        tier=result.tier,
                        local_base_url=local_llm_url or None,
                        model=local_llm_model or None,
                    )
                if explanation.available:
                    explanation_cache[cache_key] = explanation

        if explanation is not None:
            if explanation.available:
                st.info(explanation.text)
                st.caption(f"Model: {explanation.model_used}")
            else:
                st.warning(explanation.reason_unavailable)
