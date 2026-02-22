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

    return {"msg_type": "pacs.008", "fields": fields, "checks": []}

def detect_and_parse(text):
    if "<" in text and "pacs.008" in text:
        return parse_pacs008(text)

    if ":20:" in text and ":32A:" in text:
        return parse_mt103(text)

    return {"msg_type": "unknown", "fields": {}, "checks": ["Unknown format"]}
