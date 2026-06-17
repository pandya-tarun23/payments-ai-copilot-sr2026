from extractor import detect_and_parse, parse_pacs008


def test_msg_type_detected_by_root_element(structured_pacs008):
    parsed = detect_and_parse(structured_pacs008)
    assert parsed["msg_type"] == "pacs.008"


def test_envelope_wrapped_xml_still_detected_and_parsed(envelope_wrapped_pacs008):
    """SWIFT transport envelope must not break detection or field extraction."""
    parsed = detect_and_parse(envelope_wrapped_pacs008)
    assert parsed["msg_type"] == "pacs.008"
    assert parsed["fields"]["DbtrNm"] == "Acme Corp"


def test_structured_postal_addresses_extracted(structured_pacs008):
    parsed = parse_pacs008(structured_pacs008)
    assert parsed["addresses"]["debtor"] == {"TwnNm": "Dubai", "Ctry": "AE", "AdrLine": []}
    assert parsed["addresses"]["creditor"] == {"TwnNm": "London", "Ctry": "GB", "AdrLine": []}


def test_unstructured_address_extracted_as_adrline_only(unstructured_debtor_pacs008):
    parsed = parse_pacs008(unstructured_debtor_pacs008)
    debtor = parsed["addresses"]["debtor"]
    assert debtor["TwnNm"] == ""
    assert debtor["Ctry"] == ""
    assert debtor["AdrLine"] == ["P.O. Box 123, Dubai"]


def test_unknown_format_falls_back_gracefully():
    parsed = detect_and_parse("this is not a payment message")
    assert parsed["msg_type"] == "unknown"
