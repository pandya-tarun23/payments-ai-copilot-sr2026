from pathlib import Path
from typing import Any, Dict, List, Optional
import re
import yaml

from validate import validate_message  # your existing validator


BASE_DIR = Path(__file__).resolve().parent
SR2026_RULES = BASE_DIR / "rules" / "sr2026.yaml"

# CBPR+ SR2026 migration deadline — unstructured addresses forbidden after this date.
_CBPR_SR2026_DATE = "14 Nov 2026"


def load_sr2026_rules() -> Dict[str, Any]:
    if not SR2026_RULES.exists():
        raise FileNotFoundError(f"SR2026 rules file not found: {SR2026_RULES}")
    with open(SR2026_RULES, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_field(report: Dict[str, Any], field: str) -> Optional[str]:
    extracted = report.get("extracted", {})
    fields = extracted.get("fields", {}) if isinstance(extracted, dict) else {}
    v = fields.get(field)
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
    return v or None


def apply_overlay_rules(base_report: Dict[str, Any], overlay: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues = []

    for rule in overlay.get("rules", []) or []:
        rtype = rule.get("type")
        rid = rule.get("id", "SR2026_RULE")
        desc = rule.get("desc", "")
        severity = rule.get("severity", "WARN")

        if rtype == "guidance":
            issues.append({
                "severity": severity,
                "code": rid,
                "field": rule.get("field"),
                "message": f"{desc}: {rule.get('message','')}".strip()
            })
            continue

        if rtype == "in_set":
            field = rule.get("field")
            allowed = rule.get("allowed", [])
            val = _get_field(base_report, field) if field else None
            if val is None:
                issues.append({
                    "severity": "ERROR",
                    "code": rid,
                    "field": field,
                    "message": f"{desc} (field missing/empty)"
                })
            elif val not in allowed:
                issues.append({
                    "severity": "ERROR",
                    "code": rid,
                    "field": field,
                    "message": f"{desc}. Found: {val}. Allowed: {allowed}"
                })
            continue

        # unknown overlay types
        issues.append({
            "severity": "WARN",
            "code": "SR2026_UNKNOWN_RULE",
            "field": rule.get("field"),
            "message": f"Unknown SR2026 rule type: {rtype} ({rid})"
        })

    return issues


def _check_sr2026_address(addr: Dict[str, Any], party: str) -> Optional[Dict[str, Any]]:
    """
    Classify a PstlAdr block against CBPR+ SR2026 usage guidelines.

    The pacs.008 XSD still permits pure unstructured AdrLine, but CBPR+ usage
    rules forbid relying on it after 14 Nov 2026. Passing XSD validation does
    NOT mean the message is SR2026-ready — this function makes that gap explicit.

    Classification:
      unstructured   (AdrLine present, no TwnNm, no Ctry)       -> ERROR
      min-gate miss  (AdrLine present but TwnNm or Ctry absent) -> WARN
      hybrid-overflow (TwnNm+Ctry, AdrLine > 2)                 -> WARN
      hybrid / structured (TwnNm+Ctry, AdrLine <= 2)            -> compliant (None)
      empty block                                                -> None (missing-field rules handle it)
    """
    if not addr:
        return None

    has_town = bool((addr.get("TwnNm") or "").strip())
    has_ctry = bool((addr.get("Ctry") or "").strip())
    adr_lines: List[str] = addr.get("AdrLine", [])

    if not has_town and not has_ctry and not adr_lines:
        return None  # address block absent entirely — missing-field rules already flag this

    if not (has_town and has_ctry):
        if adr_lines and not has_town and not has_ctry:
            return {
                "severity": "ERROR",
                "code": "SR2026_UNSTRUCTURED_ADDR",
                "field": party,
                "message": (
                    f"{party} address is unstructured (AdrLine only, no TwnNm/Ctry). "
                    f"XSD-valid but non-compliant with CBPR+ SR2026 usage rules "
                    f"effective {_CBPR_SR2026_DATE}."
                ),
            }
        missing = [f for f, present in [("TwnNm", has_town), ("Ctry", has_ctry)] if not present]
        return {
            "severity": "WARN",
            "code": "SR2026_ADDR_MIN_GATE",
            "field": party,
            "message": (
                f"{party} address missing {'/'.join(missing)}; "
                f"CBPR+ SR2026 minimum gate requires both TwnNm and Ctry "
                f"(effective {_CBPR_SR2026_DATE})."
            ),
        }

    if len(adr_lines) > 2:
        return {
            "severity": "WARN",
            "code": "SR2026_HYBRID_OVERFLOW",
            "field": party,
            "message": (
                f"{party} hybrid address has {len(adr_lines)} AdrLine elements; "
                f"CBPR+ SR2026 permits max 2 in hybrid mode "
                f"(effective {_CBPR_SR2026_DATE})."
            ),
        }

    return None  # TwnNm + Ctry present, AdrLine <= 2 -> hybrid or fully structured


def sr2026_assess(raw_text: str) -> Dict[str, Any]:
    # Step 1: run existing validator (mandatory + base rules)
    base = validate_message(raw_text)

    # Step 2: apply SR2026 overlays
    sr = load_sr2026_rules()
    overlays = (sr.get("overlays") or {})
    norm = base.get("normalized_type")

    overlay = overlays.get(norm) or {}
    overlay_issues = apply_overlay_rules(base, overlay)

    # Step 3: real SR2026 address classification (structured/hybrid/unstructured)
    address_issues: List[Dict[str, Any]] = []
    if norm == "pacs008":
        addresses = (base.get("extracted") or {}).get("addresses") or {}
        for key, party in [("debtor", "Debtor"), ("creditor", "Creditor")]:
            finding = _check_sr2026_address(addresses.get(key) or {}, party)
            if finding:
                address_issues.append(finding)

    # Step 4: append and summarize
    base_issues = base.get("issues", [])
    all_issues = list(base_issues) + overlay_issues + address_issues

    errors = sum(1 for i in all_issues if i.get("severity") == "ERROR")
    warns = sum(1 for i in all_issues if i.get("severity") == "WARN")

    return {
        "sr_mode": "SR2026",
        "detected_type": base.get("detected_type"),
        "normalized_type": norm,
        "issues": all_issues,
        "summary": {"errors": errors, "warnings": warns},
        "extracted": base.get("extracted"),
    }


def sr2026_pretty(report: Dict[str, Any]) -> str:
    lines = []
    lines.append("SR2026 Assessment")
    lines.append(f"Type: {report.get('detected_type')}  |  Ruleset: {report.get('normalized_type')}")
    lines.append(f"Errors: {report.get('summary', {}).get('errors', 0)} | Warnings: {report.get('summary', {}).get('warnings', 0)}")
    lines.append("")

    issues = report.get("issues", []) or []
    if not issues:
        lines.append("✅ No issues found.")
        return "\n".join(lines)

    lines.append("Findings:")
    for i, it in enumerate(issues, 1):
        sev = it.get("severity")
        code = it.get("code")
        field = it.get("field")
        msg = it.get("message")
        lines.append(f"{i}. [{sev}] {code}" + (f" ({field})" if field else "") + f" — {msg}")

    lines.append("")
    lines.append("SR2026 Reminders:")
    lines.append("- Standards Release 2026 goes live on 14 Nov 2026 (plan testing well before).")
    lines.append("- SR2026 trend: tighter validation and reduced free-form data (e.g., addresses move to structured/hybrid).")
    return "\n".join(lines)
