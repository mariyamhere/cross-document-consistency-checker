
# Cross Document Consistency Checker

I made this for banks to qualify or reject commercial loan applicants based on their financial docs. It checks whether a bank statement's credits match a declared income figure. Runs offline. Deterministic checks, no AI required. An optional local LLM can explain flagged gaps.

Demo URL: [found-a-discrepency-or-not.streamlit.app](https://found-a-discrepency-or-not.streamlit.app)

<img width="1879" height="910" alt="image" src="https://github.com/user-attachments/assets/1273585a-0580-41fa-9765-93872a939a53" />

## What it does

1. Parses a transaction level bank statement PDF and sums total credits.
2. Extracts a declared income figure from a second document, or takes it as manual input.
3. Compares the two using fixed thresholds and returns one of: Match, Variance, Discrepancy.
4. Optionally, a local LLM (Ollama, LM Studio, or any OpenAI compatible endpoint) suggests reasons for a flagged gap. Advisory only, never changes the result.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```
- Extraction is regex based and layout specific. It matches the sample documents' format; a different bank's statement layout will need its own parser.
- Thresholds in `core/reconcile.py` are illustrative defaults, not validated lending policy.
- No data leaves your machine unless a local LLM endpoint is configured, and even then only the computed figures (not the source documents) are sent.
