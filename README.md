# Payments AI Copilot — SR2026 Assistant

AI-powered validation and investigation tool for ISO 20022 CBPR+ SR2026 payments.

## SR2026 Address Classification

The centerpiece of this project: CBPR+ Standards Release 2026 (effective 14 Nov 2026)
phases out free-form postal addresses on pacs.008 messages. XSD validation alone
won't catch this — the schema still permits pure unstructured `AdrLine` blocks, so a
message can be XSD-valid today and still be rejected under SR2026 usage rules.

This tool extracts each party's `PstlAdr` block (`TwnNm`, `Ctry`, `AdrLine`) and
classifies it:

| Address shape | Example | Result |
|---|---|---|
| Unstructured (`AdrLine` only, no `TwnNm`/`Ctry`) | `<AdrLine>P.O. Box 123, Dubai</AdrLine>` | `ERROR` — non-compliant after SR2026 |
| Minimum-gate miss (`TwnNm` or `Ctry` absent) | `<TwnNm>London</TwnNm>` (no `Ctry`) | `WARN` |
| Hybrid overflow (`TwnNm`+`Ctry` present, >2 `AdrLine`) | structured + 3 address lines | `WARN` |
| Structured / compliant hybrid (`TwnNm`+`Ctry`, ≤2 `AdrLine`) | `<TwnNm>London</TwnNm><Ctry>GB</Ctry>` | OK |

Run it via **SR2026 Assessment** or **Autopilot** mode — paste a pacs.008 message and
get a per-party classification alongside the rest of the rule findings.

<!-- Run `streamlit run app.py`, paste a pacs.008 message with an unstructured
     address, run SR2026 Assessment, and save the result as docs/sr2026_screenshot.png -->
![SR2026 Assessment screenshot](docs/sr2026_screenshot.png)

## Other Features

- pacs.008 XSD validation (SR2026 schema)
- Rules-based validation (MT103 + pacs.008)
- Failure analysis of pacs.002 rejection codes
- AI-generated remediation suggestions (via local Ollama LLM)
- Autopilot mode (auto-detects message/incident type and runs the right checks)

## Use Cases

- ISO 20022 migration testing
- Payments operations investigation
- Training and knowledge support

## Setup

```bash
pip install -r requirements.txt
```

The app and CLI agent use a local [Ollama](https://ollama.com) instance
(`llama3.1:8b` for generation, `nomic-embed-text` for embeddings) — install Ollama
and pull both models before running.

Run the Streamlit app:

```bash
streamlit run app.py
```

## XSD Schema Setup

XSD Validation mode (and Autopilot's XSD check) validates pacs.008 messages against
SWIFT's CBPR+ SR2026 schema. That schema is **licensed by SWIFT and is not included
in this repo** — `rules/xsd/` is gitignored on purpose.

To use XSD Validation mode, either:

- Place your own copy at:
  `rules/xsd/sr2026_pacs008/CBPRPlus_SR2026_(Combined)_CBPRPlus-pacs_008_001_08_FIToFICustomerCreditTransfer_20260209_0820_iso15enriched.xsd`
- Or set the `SR2026_XSD_PATH` environment variable to point at your schema file elsewhere.

Without a schema configured, every other mode (Validate, SR2026 Assessment, Failure
Analysis, Autopilot) still works — only the XSD checks will show a warning instead
of running.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Disclaimer

This is a demo project using synthetic data.  
No real customer or bank data is included.

## Author

Tarun Pandya — Payments Transformation Specialist
