import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

from validate import validate_message, pretty_defects
from sr2026 import sr2026_assess, sr2026_pretty
from xsd_validate import validate_xml_against_xsd
from failure_analyzer import analyze_failure, pretty_failure, ai_suggestion


UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")


def detect_input_kind(text: str) -> str:
    t = (text or "").strip()

    # Obvious command overrides (if user still types them)
    if t.lower().startswith(("validate:", "sr2026:", "xsd_validate:", "failure_analysis:")):
        return "command"

    # XML detection
    if "<" in t and ">" in t and t.lstrip().startswith("<"):
        low = t.lower()
        if "pacs.002" in low or "fitofipmtstsrpt" in low:
            return "pacs002_xml"
        if "pacs.008" in low or "fitoficstmrcdttrf" in low:
            return "pacs008_xml"
        return "xml_other"

    # MT-ish detection
    if ":20:" in t and (":32A:" in t or ":23B:" in t):
        return "mt_like"

    # Incident text heuristics
    if any(k in t.lower() for k in ["rjct", "reject", "rejected", "return", "failed", "ac04", "ac01", "ag01", "am04"]):
        return "incident_text"

    return "free_text"


def run_autopilot(
    text: str,
    llm=None,
    xsd_path: Path | None = None,
) -> Dict[str, Any]:
    """
    Returns a structured result with multiple sections.
    Streamlit and CLI can render these sections.
    """
    kind = detect_input_kind(text)
    out: Dict[str, Any] = {"kind": kind, "sections": []}

    # If user typed an explicit command, let caller handle it elsewhere
    if kind == "command":
        out["sections"].append(("INFO", "Detected explicit command. Autopilot skipped."))
        return out

    # pacs.002: failure analysis (+ AI)
    if kind == "pacs002_xml":
        rep = analyze_failure(text)
        out["sections"].append(("FAILURE_ANALYSIS", pretty_failure(rep)))
        if llm is not None:
            out["sections"].append(("AI_SUGGESTIONS", ai_suggestion(llm, rep)))
        return out

    # pacs.008: run XSD + SR2026 + base rules (+ optional AI suggestions using failure analyzer on text)
    if kind == "pacs008_xml":
        if xsd_path is not None:
            ok, errs = validate_xml_against_xsd(text, xsd_path)
            if ok:
                out["sections"].append(("XSD", "✅ XSD VALID (SR2026 pacs.008)"))
            else:
                out["sections"].append(("XSD", "❌ XSD INVALID (SR2026 pacs.008)\n" + "\n".join(errs[:50])))

        # SR2026 overlays (your rules)
        sr = sr2026_assess(text)
        out["sections"].append(("SR2026", sr2026_pretty(sr)))

        # Base rules validation
        base = validate_message(text)
        out["sections"].append(("RULES_VALIDATE", pretty_defects(base)))

        # If it looks “problematic”, offer AI suggestions (based on findings)
        if llm is not None:
            # Feed a compact “incident summary” to the analyzer for AI tips
            # (We reuse your ai_suggestion by creating a minimal report-like dict)
            summary_like = {
                "overview": {
                    "reason_code": "VALIDATION_FINDINGS",
                    "reason_meaning": "XSD/SR2026/Rules findings detected",
                    "uetr": _extract_uetr(text),
                }
            }
            out["sections"].append(("AI_SUGGESTIONS", ai_suggestion(llm, summary_like)))

        return out

    # MT: base validate (+ SR2026 note)
    if kind == "mt_like":
        base = validate_message(text)
        out["sections"].append(("RULES_VALIDATE", pretty_defects(base)))
        out["sections"].append(("SR2026", "SR2026 mainly applies to MX/CBPR+ usage. For MT, focus on MX readiness & mapping tests."))
        return out

    # Incident text: failure analysis (+ AI)
    if kind == "incident_text":
        rep = analyze_failure(text)
        out["sections"].append(("FAILURE_ANALYSIS", pretty_failure(rep)))
        if llm is not None:
            out["sections"].append(("AI_SUGGESTIONS", ai_suggestion(llm, rep)))
        return out

    # Free text: treat as Q&A (caller can route to RAG)
    out["sections"].append(("INFO", "Looks like a normal question. Route to RAG / knowledge-base answer."))
    return out


def _extract_uetr(text: str) -> str | None:
    m = UUID_RE.search(text or "")
    return m.group(0) if m else None