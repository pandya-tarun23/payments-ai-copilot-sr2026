import re
from lxml import etree


def parse_mt103(text):
    fields = {}

    def find(tag):
        m = re.search(rf":{tag}:(.*?)(?=\n:|\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else None

    for t in ["20", "23B", "32A", "50K", "59", "71A", "121"]:
        v = find(t)
        if v:
            fields[t] = v

    return {"msg_type": "MT103", "fields": fields, "checks": []}


from lxml import etree

def _extract_postal_address(root, party):
    """
    Extract PstlAdr sub-fields (TwnNm, Ctry, AdrLine) for a party ('Dbtr' or 'Cdtr').
    Used for SR2026 address classification (structured vs hybrid vs unstructured).
    """
    base = f"//*[local-name()='{party}']/*[local-name()='PstlAdr']"
    twn = root.xpath(f"{base}/*[local-name()='TwnNm']/text()")
    ctry = root.xpath(f"{base}/*[local-name()='Ctry']/text()")
    adr_lines = root.xpath(f"{base}/*[local-name()='AdrLine']/text()")

    return {
        "TwnNm": twn[0].strip() if twn else "",
        "Ctry": ctry[0].strip().upper() if ctry else "",
        "AdrLine": [a.strip() for a in adr_lines if a and a.strip()],
    }

def parse_pacs008(xml_text):
    root = etree.fromstring(xml_text.encode())

    def x(xpath):
        res = root.xpath(xpath)
        if not res:
            return None
        # if XPath returns a string/text result
        if isinstance(res[0], str):
            return res[0].strip() or None
        # if XPath returns an element
        if hasattr(res[0], "text"):
            return (res[0].text or "").strip() or None
        return str(res[0]).strip() or None

    fields = {
        "MsgId": x("//*[local-name()='GrpHdr']/*[local-name()='MsgId']/text()"),
        "CreDtTm": x("//*[local-name()='GrpHdr']/*[local-name()='CreDtTm']/text()"),
        "InstrId": x("//*[local-name()='PmtId']/*[local-name()='InstrId']/text()"),
        "EndToEndId": x("//*[local-name()='PmtId']/*[local-name()='EndToEndId']/text()"),
        "IntrBkSttlmAmt": x("//*[local-name()='IntrBkSttlmAmt']/text()"),
        "DbtrNm": x("//*[local-name()='Dbtr']//*[local-name()='Nm']/text()"),
        "CdtrNm": x("//*[local-name()='Cdtr']//*[local-name()='Nm']/text()"),
        "ChrgBr": x("//*[local-name()='ChrgBr']/text()"),
        "UETR": x("//*[local-name()='UETR']/text()"),
    }

    # ✅ Extract currency attribute: <IntrBkSttlmAmt Ccy="USD">100.50</IntrBkSttlmAmt>
    try:
        amt_nodes = root.xpath("//*[local-name()='IntrBkSttlmAmt']")
        if amt_nodes:
            ccy = amt_nodes[0].get("Ccy")
            if ccy:
                fields["Ccy"] = ccy.strip()
    except Exception:
        pass

    addresses = {
        "debtor": _extract_postal_address(root, "Dbtr"),
        "creditor": _extract_postal_address(root, "Cdtr"),
    }

    return {"msg_type": "pacs.008", "fields": fields, "checks": [], "addresses": addresses}

def detect_and_parse(text):
    t = text or ""
    low = t.lower()

    # Detect by root element local-name (namespace-agnostic), not just a
    # "pacs.008" substring — mirrors the heuristic already used in autopilot.py.
    if "<" in t and ("fitoficstmrcdttrf" in low or "pacs.008" in low):
        return parse_pacs008(t)

    if ":20:" in t and ":32A:" in t:
        return parse_mt103(t)

    return {"msg_type": "unknown", "fields": {}, "checks": ["Unknown format"]}
