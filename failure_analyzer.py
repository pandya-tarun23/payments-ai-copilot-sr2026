import re
from typing import Any, Dict, List, Optional

from lxml import etree

from extractor import detect_and_parse


# Starter dictionary (extend anytime)
PACS002_CODES = {
    "AC04": {
        "meaning": "Account closed",
        "checks": [
            "Creditor account/IBAN in original message correct?",
            "Is creditor account closed/blocked/dormant at beneficiary bank?",
            "Was account format changed/mapped incorrectly during MT→MX conversion?",
        ],
        "ask": [
            "Confirm beneficiary account status and closure date",
            "Provide beneficiary bank reject details and internal reference",
        ],
    },
    "AM04": {
        "meaning": "Insufficient funds",
        "checks": [
            "Is this a return/refund scenario requiring special handling?",
            "Any limits/overdraft constraints at beneficiary/receiver side?",
        ],
        "ask": [
            "Confirm where insufficient funds occurred and which account context",
            "Any overdraft/limit constraints or cut-off timing?",
        ],
    },
    "AG01": {
        "meaning": "Transaction forbidden",
        "checks": [
            "Sanctions/AML screening hit?",
            "Local regulatory/product restriction triggered?",
            "Purpose/category purpose constraints breached for corridor/scheme?",
        ],
        "ask": [
            "Which compliance rule triggered? (sanctions/AML/velocity/geo)",
            "Is additional information required for repair/release?",
        ],
    },
    "BE04": {
        "meaning": "Invalid creditor account number",
        "checks": [
            "IBAN/account checksum/length correct?",
            "Account mapped incorrectly from legacy fields?",
        ],
        "ask": [
            "Expected account/IBAN format for corridor",
            "Confirm whether account exists at beneficiary bank",
        ],
    },
}

PACS002_CODES.update({
    "AC01": {
        "meaning": "Incorrect account number (invalid format/wrong account)",
        "checks": [
            "Validate IBAN/account checksum/length and country rules",
            "Verify account is in the correct ISO element (and not truncated)",
            "If MT→MX conversion involved, verify mapping to creditor account",
        ],
        "ask": [
            "Confirm which account field failed validation and expected format",
            "Confirm whether the account exists at beneficiary bank",
        ],
    },
    "AC03": {
        "meaning": "Invalid creditor account number or not provided",
        "checks": [
            "Confirm creditor account present and correctly populated",
            "Check for truncation/whitespace/invalid characters",
            "Verify mapping from legacy/account source fields",
        ],
        "ask": [
            "Is the account missing or invalid? Provide expected format for the corridor",
        ],
    },
    "AC06": {
        "meaning": "Account blocked / not usable",
        "checks": [
            "Confirm whether block is account-status vs compliance hold",
            "Check if beneficiary account is dormant/frozen/blocked",
        ],
        "ask": [
            "Is the block due to account status or compliance? What is needed to release/repair?",
        ],
    },
    "AC13": {
        "meaning": "Invalid debtor account",
        "checks": [
            "Validate debtor account format and existence in core",
            "Verify correct mapping of debtor account from channel/core to message",
        ],
        "ask": [
            "Confirm debtor account validation failure details (which element and why)",
        ],
    },
    "AC14": {
        "meaning": "Invalid agent/account servicer context",
        "checks": [
            "Verify DebtorAgent/CreditorAgent identifiers (BIC/clearing member id)",
            "Check intermediary chain/routing rules for the corridor",
        ],
        "ask": [
            "Which agent identifier is invalid (BIC/clearing id)? Provide expected routing",
        ],
    },
    "AC15": {
        "meaning": "Account name mismatch / invalid account holder details",
        "checks": [
            "Check name verification or beneficiary name rules (scheme/bank-specific)",
            "Confirm ordering/beneficiary name mapping and allowed characters",
        ],
        "ask": [
            "Is this a name-check failure? What name format is required for acceptance?",
        ],
    },
    "AC16": {
        "meaning": "Account does not exist",
        "checks": [
            "Confirm beneficiary account exists and is active",
            "Verify no digit loss during mapping/transmission",
        ],
        "ask": [
            "Confirm whether account exists; if not, can beneficiary provide the correct account?",
        ],
    },
    "AC17": {
        "meaning": "Account transferred/switched (successor account may exist)",
        "checks": [
            "Check if beneficiary moved accounts/banks and whether redirection exists",
        ],
        "ask": [
            "Is there a successor account? Provide new account details for re-initiation",
        ],
    },
    "AG02": {
        "meaning": "Invalid bank operation code / operation not supported",
        "checks": [
            "Check ServiceLevel/LocalInstrument/CategoryPurpose values",
            "Confirm corridor/scheme capability and message variant support",
        ],
        "ask": [
            "Which operation/value is unsupported? What values do you accept for this corridor?",
        ],
    },
    "AM01": {
        "meaning": "Invalid amount",
        "checks": [
            "Check decimal separator and numeric format",
            "Check currency fraction digits and rounding rules",
        ],
        "ask": [
            "Is the issue format/precision or a business limit? Provide allowed precision/limits",
        ],
    },
    "AM02": {
        "meaning": "Amount exceeds limit",
        "checks": [
            "Confirm scheme/bank corridor limits and product caps",
            "Consider split payment if permitted",
        ],
        "ask": [
            "What is the max allowed amount? Is splitting permitted?",
        ],
    },
    "AM03": {
        "meaning": "Currency not supported",
        "checks": [
            "Confirm corridor supports instructed/settlement currency",
            "Check settlement currency vs instructed currency mismatch",
        ],
        "ask": [
            "Which currencies are supported for this corridor? Should settlement currency be changed?",
        ],
    },
    "AM05": {
        "meaning": "Duplicate transaction",
        "checks": [
            "Check if same MsgId/InstrId/EndToEndId/UETR was resent",
            "Review retry/idempotency logic and replay mechanisms",
        ],
        "ask": [
            "Which reference triggered duplicate detection? Provide the original reference on your side",
        ],
    },
    "DUPL": {
        "meaning": "Payment is a duplicate of another payment",
        "checks": [
            "Verify idempotency keys / unique references and resubmission strategy",
            "Check if payment was resent after timeout and actually processed previously",
        ],
        "ask": [
            "Provide reference of the original payment you consider duplicate",
        ],
    },
})

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        x2 = (x or "").strip()
        if x2 and x2 not in seen:
            out.append(x2)
            seen.add(x2)
    return out


def _xml_first_text(root: etree._Element, xpath: str) -> Optional[str]:
    try:
        res = root.xpath(xpath)  # do NOT pass namespaces; use local-name() paths
    except Exception:
        return None
    if not res:
        return None
    if isinstance(res[0], str):
        v = res[0].strip()
        return v or None
    if hasattr(res[0], "text"):
        v = (res[0].text or "").strip()
        return v or None
    v = str(res[0]).strip()
    return v or None


def parse_pacs002_details(xml_text: str) -> Dict[str, Any]:
    """
    Extracts common failure-analysis fields from pacs.002 regardless of namespace/version.
    """
    out: Dict[str, Any] = {"msg_type": "pacs.002", "fields": {}, "checks": []}

    try:
        root = etree.fromstring(xml_text.encode("utf-8"))
    except Exception as e:
        out["checks"].append(f"XML parse failed: {e}")
        return out

    # Transaction / group status
    grp_sts = _xml_first_text(root, "//*[local-name()='OrgnlGrpInfAndSts']/*[local-name()='GrpSts']/text()")
    tx_sts = _xml_first_text(root, "//*[local-name()='TxInfAndSts']/*[local-name()='TxSts']/text()")
    out["fields"]["GrpSts"] = grp_sts
    out["fields"]["TxSts"] = tx_sts

    # Reason code (most important)
    rsn_cd = _xml_first_text(root, "//*[local-name()='StsRsnInf']/*[local-name()='Rsn']/*[local-name()='Cd']/text()")
    rsn_prtry = _xml_first_text(root, "//*[local-name()='StsRsnInf']/*[local-name()='Rsn']/*[local-name()='Prtry']/text()")
    out["fields"]["RsnCd"] = rsn_cd
    out["fields"]["RsnPrtry"] = rsn_prtry

    # Additional info
    addtl_inf = _xml_first_text(root, "//*[local-name()='StsRsnInf']/*[local-name()='AddtlInf']/text()")
    out["fields"]["AddtlInf"] = addtl_inf

    # Original identifiers (very useful for correlation)
    out["fields"]["OrgnlMsgId"] = _xml_first_text(root, "//*[local-name()='OrgnlGrpInfAndSts']/*[local-name()='OrgnlMsgId']/text()")
    out["fields"]["OrgnlMsgNmId"] = _xml_first_text(root, "//*[local-name()='OrgnlGrpInfAndSts']/*[local-name()='OrgnlMsgNmId']/text()")
    out["fields"]["OrgnlCreDtTm"] = _xml_first_text(root, "//*[local-name()='OrgnlGrpInfAndSts']/*[local-name()='OrgnlCreDtTm']/text()")

    out["fields"]["OrgnlInstrId"] = _xml_first_text(root, "//*[local-name()='OrgnlInstrId']/text()")
    out["fields"]["OrgnlEndToEndId"] = _xml_first_text(root, "//*[local-name()='OrgnlEndToEndId']/text()")
    out["fields"]["OrgnlUETR"] = _xml_first_text(root, "//*[local-name()='OrgnlUETR']/text()")

    # UETR can appear as UETR too (some variants)
    out["fields"]["UETR"] = _xml_first_text(root, "//*[local-name()='UETR']/text()")

    return out


def _guess_reason_code_from_text(text: str) -> Optional[str]:
    # fallback only
    m = re.search(r"\b([A-Z]{2}\d{2})\b", text)
    return m.group(1) if m else None


def _extract_uetr_anywhere(text: str) -> Optional[str]:
    m = UUID_RE.search(text)
    return m.group(0) if m else None


def recommended_actions(code: Optional[str]) -> List[str]:
    base = [
        "1) Confirm exact status + reason from pacs.002 (GrpSts/TxSts + Rsn/Cd + AddtlInf).",
        "2) Correlate across logs using UETR + OrgnlMsgId/InstrId/EndToEndId (and internal reference).",
        "3) Decide path: REPAIR/RESEND vs RETURN vs CANCEL (camt.056) based on scheme rules and bank procedures.",
        "4) If mapping issue suspected: reproduce in lower env with same payload, fix mapping, then follow controlled prod repair.",
        "5) Record a Jira defect: symptoms, exact code, impacted fields, proposed fix, evidence (logs + message copies).",
    ]
    if code in {"AC04", "BE04"}:
        base.insert(3, "3a) Account issue: confirm beneficiary account details with receiving bank; do NOT resend blindly without correction.")
    if code in {"AG01"}:
        base.insert(3, "3a) Forbidden/compliance: involve AML/Compliance; collect required info and follow repair workflow.")
    return base


def build_investigation_email(rep: Dict[str, Any]) -> Dict[str, str]:
    """
    Creates a subject + body you can paste into email/chat (no sending).
    """
    o = rep.get("overview", {})
    code = o.get("reason_code")
    code_meaning = o.get("reason_meaning")
    uetr = o.get("uetr")
    org_msg_id = o.get("original_msg_id")
    org_instr = o.get("original_instr_id")
    e2e = o.get("original_end_to_end_id")

    subject = f"Investigation: Payment status {o.get('status','')} {code or ''} {('- ' + code_meaning) if code_meaning else ''}".strip()

    lines = []
    lines.append("Hello Team,")
    lines.append("")
    lines.append("We received a payment status indicating a failure. Please help confirm the exact rejection details and required corrective action.")
    lines.append("")
    lines.append("Key references:")
    if uetr:
        lines.append(f"- UETR: {uetr}")
    if org_msg_id:
        lines.append(f"- Original MsgId: {org_msg_id}")
    if org_instr:
        lines.append(f"- Original InstrId: {org_instr}")
    if e2e:
        lines.append(f"- Original EndToEndId: {e2e}")
    if code:
        lines.append(f"- Reason code: {code}" + (f" ({code_meaning})" if code_meaning else ""))
    if o.get("addtl_info"):
        lines.append(f"- Additional info: {o.get('addtl_info')}")
    lines.append("")
    lines.append("Please confirm:")
    lines.append("1) The exact rejection reason and any mandatory data required for repair/re-submission")
    lines.append("2) Whether this should be repaired, returned, or cancelled (per your scheme/corridor rules)")
    lines.append("3) Any internal reference/ticket number for tracking on your side")
    lines.append("")
    lines.append("Thanks,")
    lines.append("Operations Team")
    body = "\n".join(lines)

    return {"subject": subject, "body": body}


def analyze_failure(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()

    # If it's pacs.002 XML, parse it explicitly for reason code + original refs
    pacs002 = None
    if "<" in raw and "pacs.002" in raw:
        pacs002 = parse_pacs002_details(raw)

    parsed = detect_and_parse(raw)  # MT103/pacs.008 parsing, or unknown
    msg_type = parsed.get("msg_type", "unknown")
    fields = parsed.get("fields") or {}

    # Determine code/status
    rsn_cd = None
    status = None
    addtl = None
    org_msg_id = None
    org_instr = None
    org_e2e = None
    org_uetr = None

    if pacs002:
        p = pacs002.get("fields") or {}
        rsn_cd = p.get("RsnCd") or p.get("RsnPrtry")
        status = p.get("TxSts") or p.get("GrpSts")
        addtl = p.get("AddtlInf")
        org_msg_id = p.get("OrgnlMsgId")
        org_instr = p.get("OrgnlInstrId")
        org_e2e = p.get("OrgnlEndToEndId")
        org_uetr = p.get("OrgnlUETR") or p.get("UETR")

    if not rsn_cd:
        rsn_cd = _guess_reason_code_from_text(raw)

    code_info = PACS002_CODES.get(rsn_cd) if rsn_cd else None

    # Correlate UETR across sources
    uetr = fields.get("121") or fields.get("UETR") or org_uetr or _extract_uetr_anywhere(raw)

    # Some normalization hints
    chrg = fields.get("71A") or fields.get("ChrgBr")
    ccy = fields.get("Ccy")
    amt = fields.get("IntrBkSttlmAmt") or fields.get("32A")

    overview = {
        "detected_message_type": pacs002["msg_type"] if pacs002 else msg_type,
        "status": status,
        "reason_code": rsn_cd,
        "reason_meaning": code_info["meaning"] if code_info else None,
        "addtl_info": addtl,
        "uetr": uetr,
        "original_msg_id": org_msg_id,
        "original_instr_id": org_instr,
        "original_end_to_end_id": org_e2e,
        "amount_hint": amt,
        "currency": ccy,
        "charges_hint": chrg,
        "debtor_hint": fields.get("50K") or fields.get("DbtrNm"),
        "creditor_hint": fields.get("59") or fields.get("CdtrNm"),
    }

    checks: List[str] = []
    asks: List[str] = []
    summary: List[str] = []

    if code_info:
        summary.append(f"Reason code {rsn_cd}: {code_info['meaning']}")
        checks.extend(code_info["checks"])
        asks.extend(code_info["ask"])
    else:
        summary.append("Reason code not confidently identified. Prefer pacs.002 <StsRsnInf><Rsn><Cd>/<Prtry> if available.")
        checks.extend([
            "Capture exact pacs.002 status + reason and additional info",
            "Verify MsgId/InstrId/EndToEndId/UETR consistency across hops",
        ])
        asks.extend([
            "Ask receiving bank for exact rejection reason code and additional info",
            "Ask for their internal reference / investigation ticket number",
        ])

    # Always-useful checks
    checks.extend([
        "Confirm corridor & scheme rules (CBPR+, local clearing, correspondent chain).",
        "Confirm whether this is REJECT vs RETURN vs REPAIR scenario (procedure differs).",
        "Check sanctions/AML screening hits (names, addresses, countries) if forbidden/blocked hints appear.",
        "If MT→MX conversion involved, verify mapping for account/agent fields and address blocks.",
        "If SR2026 readiness: confirm address structuring/hybrid compliance where applicable.",
    ])

    if uetr:
        summary.append(f"Use UETR to trace across gpi/internal logs: {uetr}")
    if org_msg_id:
        summary.append(f"Correlate using OrgnlMsgId: {org_msg_id}")

    rep = {
        "overview": overview,
        "summary": summary,
        "what_to_check": _dedupe(checks),
        "what_to_ask_other_bank": _dedupe(asks),
        "recommended_next_actions": recommended_actions(rsn_cd),
    }

    rep["investigation_email"] = build_investigation_email(rep)
    return rep


def pretty_failure(rep: Dict[str, Any]) -> str:
    o = rep["overview"]
    lines = []
    lines.append("Failure Analysis")
    lines.append(f"- Type: {o.get('detected_message_type')}")
    if o.get("status"):
        lines.append(f"- Status: {o.get('status')}")
    if o.get("reason_code"):
        meaning = o.get("reason_meaning")
        lines.append(f"- Reason: {o.get('reason_code')}" + (f" ({meaning})" if meaning else ""))
    if o.get("addtl_info"):
        lines.append(f"- Additional info: {o.get('addtl_info')}")
    if o.get("uetr"):
        lines.append(f"- UETR: {o.get('uetr')}")
    if o.get("original_msg_id"):
        lines.append(f"- OrgnlMsgId: {o.get('original_msg_id')}")
    if o.get("original_instr_id"):
        lines.append(f"- OrgnlInstrId: {o.get('original_instr_id')}")
    if o.get("original_end_to_end_id"):
        lines.append(f"- OrgnlEndToEndId: {o.get('original_end_to_end_id')}")
    lines.append("")

    lines.append("Summary")
    for s in rep.get("summary", []):
        lines.append(f"- {s}")
    lines.append("")

    lines.append("What to check")
    for i, c in enumerate(rep["what_to_check"], 1):
        lines.append(f"{i}. {c}")
    lines.append("")

    lines.append("What to ask the other bank")
    for i, a in enumerate(rep["what_to_ask_other_bank"], 1):
        lines.append(f"{i}. {a}")
    lines.append("")

    lines.append("Recommended next actions")
    for a in rep["recommended_next_actions"]:
        lines.append(f"- {a}")
    lines.append("")

    email = rep.get("investigation_email", {})
    if email:
        lines.append("Investigation email draft")
        lines.append(f"Subject: {email.get('subject','')}")
        lines.append(email.get("body", ""))

    return "\n".join(lines)

def ai_suggestion(llm, report):

    overview = report.get("overview", {})

    reason = overview.get("reason_code", "Unknown")
    meaning = overview.get("reason_meaning", "")
    uetr = overview.get("uetr", "")

    prompt = f"""
You are a senior SWIFT CBPR+ operations expert specializing in cross-border payments investigation.

Provide remediation suggestions for this payment failure.

Reason code: {reason}
Meaning: {meaning}
UETR: {uetr}

Give concise bullet points:

• Likely root causes
• Immediate actions
• Repair / resend strategy
• Questions to ask other bank
• Preventive controls

Keep it practical and aligned to CBPR+ processes.
"""

    result = llm.invoke(prompt)

    # Ensure output is not blank
    if not result or not str(result).strip():
        return "⚠️ No AI suggestion generated. Try again."

    return str(result).strip()