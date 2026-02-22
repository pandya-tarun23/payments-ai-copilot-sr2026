import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from extractor import detect_and_parse


BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = BASE_DIR / "rules" / "rules.yaml"


def load_rules() -> Dict[str, Any]:
    if not RULES_PATH.exists():
        raise FileNotFoundError(f"Rules file not found: {RULES_PATH}")
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def normalize_msg_type(msg_type: str) -> str:
    t = (msg_type or "").strip().lower()
    if t == "mt103":
        return "mt103"
    if t in {"pacs.008", "pacs008"}:
        return "pacs008"
    return t


def get_field(parsed: Dict[str, Any], key: str) -> Optional[str]:
    """
    MT103 -> parsed["fields"][tag]
    pacs.008 -> parsed["fields"][key]
    """
    fields = parsed.get("fields") or {}
    val = fields.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        v = val.strip()
        return v if v else None
    return str(val).strip() or None


def check_mandatory(parsed: Dict[str, Any], mandatory_fields: List[str]) -> List[Dict[str, Any]]:
    issues = []
    for f in mandatory_fields:
        if not get_field(parsed, f):
            issues.append({
                "severity": "ERROR",
                "code": "MISSING_MANDATORY",
                "field": f,
                "message": f"Missing mandatory field: {f}"
            })
    return issues


def run_rule(parsed: Dict[str, Any], rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rtype = rule.get("type")
    field = rule.get("field")
    rid = rule.get("id", "RULE")
    desc = rule.get("desc", "")

    val = get_field(parsed, field) if field else None

    if rtype == "regex_field":
        if not val:
            return {
                "severity": "ERROR",
                "code": rid,
                "field": field,
                "message": f"{desc} (field missing/empty)"
            }
        pat = rule.get("pattern", "")
        if not re.match(pat, val):
            return {
                "severity": "ERROR",
                "code": rid,
                "field": field,
                "message": f"{desc}. Found: {val}"
            }
        return None

    if rtype == "regex_optional":
        if not val:
            return None
        pat = rule.get("pattern", "")
        if not re.match(pat, val):
            return {
                "severity": "WARN",
                "code": rid,
                "field": field,
                "message": f"{desc}. Found: {val}"
            }
        return None

    if rtype == "in_set":
        if not val:
            return {
                "severity": "ERROR",
                "code": rid,
                "field": field,
                "message": f"{desc} (field missing/empty)"
            }
        allowed = rule.get("allowed", [])
        if val not in allowed:
            return {
                "severity": "ERROR",
                "code": rid,
                "field": field,
                "message": f"{desc}. Found: {val}. Allowed: {allowed}"
            }
        return None

    # Unknown rule type
    return {
        "severity": "WARN",
        "code": "UNKNOWN_RULE_TYPE",
        "field": field,
        "message": f"Unknown rule type: {rtype} for rule {rid}"
    }


def validate_message(raw_text: str) -> Dict[str, Any]:
    rules_all = load_rules()
    parsed = detect_and_parse(raw_text)
    msg_type_raw = parsed.get("msg_type", "unknown")
    msg_type = normalize_msg_type(msg_type_raw)

    report: Dict[str, Any] = {
        "detected_type": msg_type_raw,
        "normalized_type": msg_type,
        "extracted": parsed,
        "issues": [],
        "summary": {}
    }

    if msg_type not in rules_all:
        report["issues"].append({
            "severity": "WARN",
            "code": "NO_RULESET",
            "field": None,
            "message": f"No ruleset found for message type: {msg_type_raw}"
        })
        report["summary"] = {
            "errors": 0,
            "warnings": 1
        }
        return report

    ruleset = rules_all[msg_type]
    mandatory = ruleset.get("mandatory_fields", [])
    rules = ruleset.get("rules", [])

    issues = []
    issues.extend(check_mandatory(parsed, mandatory))

    for r in rules:
        issue = run_rule(parsed, r)
        if issue:
            issues.append(issue)

    # Add parser checks (from extractor) if any
    for c in parsed.get("checks", []) or []:
        issues.append({
            "severity": "WARN",
            "code": "PARSER_CHECK",
            "field": None,
            "message": str(c)
        })

    report["issues"] = issues
    errors = sum(1 for i in issues if i.get("severity") == "ERROR")
    warns = sum(1 for i in issues if i.get("severity") == "WARN")
    report["summary"] = {"errors": errors, "warnings": warns}
    return report


def pretty_defects(report: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Detected: {report.get('detected_type')}  |  Ruleset: {report.get('normalized_type')}")
    lines.append(f"Errors: {report.get('summary', {}).get('errors', 0)} | Warnings: {report.get('summary', {}).get('warnings', 0)}")
    lines.append("")

    issues = report.get("issues", [])
    if not issues:
        lines.append("✅ No issues found.")
        return "\n".join(lines)

    lines.append("Defects:")
    for i, it in enumerate(issues, 1):
        sev = it.get("severity")
        code = it.get("code")
        field = it.get("field")
        msg = it.get("message")
        lines.append(f"{i}. [{sev}] {code}" + (f" ({field})" if field else "") + f" — {msg}")
    return "\n".join(lines)


if __name__ == "__main__":
    raw = input("Paste message (MT103 or pacs.008 XML), then Enter:\n")
    rep = validate_message(raw)
    print(pretty_defects(rep))
