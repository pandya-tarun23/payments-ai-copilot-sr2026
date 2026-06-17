from sr2026 import _check_sr2026_address, sr2026_assess


# ---------------------------------------------------------------------------
# SR2026 address classification (unit)
# ---------------------------------------------------------------------------

def test_unstructured_address_fires_error():
    """AdrLine only, no TwnNm/Ctry -- XSD-valid but forbidden by CBPR+ SR2026."""
    addr = {"TwnNm": "", "Ctry": "", "AdrLine": ["P.O. Box 123, Dubai"]}
    finding = _check_sr2026_address(addr, "Debtor")
    assert finding is not None
    assert finding["code"] == "SR2026_UNSTRUCTURED_ADDR"
    assert finding["severity"] == "ERROR"


def test_hybrid_address_within_cap_is_compliant():
    """TwnNm + Ctry + one AdrLine is the allowed hybrid form -- no finding."""
    addr = {"TwnNm": "London", "Ctry": "GB", "AdrLine": ["10 King Street"]}
    assert _check_sr2026_address(addr, "Creditor") is None


def test_fully_structured_address_is_compliant():
    """TwnNm + Ctry, no AdrLine -- best-practice structured form."""
    addr = {"TwnNm": "Frankfurt", "Ctry": "DE", "AdrLine": []}
    assert _check_sr2026_address(addr, "Debtor") is None


def test_hybrid_overflow_exceeds_two_adrline_cap():
    """TwnNm + Ctry present but three AdrLine elements -- violates the hybrid cap."""
    addr = {"TwnNm": "Dubai", "Ctry": "AE", "AdrLine": ["Suite 501", "Tower B", "Business Bay"]}
    finding = _check_sr2026_address(addr, "Creditor")
    assert finding is not None
    assert finding["code"] == "SR2026_HYBRID_OVERFLOW"
    assert finding["severity"] == "WARN"


def test_min_gate_ctry_only_fires_warn():
    """Ctry present but TwnNm absent -- minimum gate (TwnNm AND Ctry) not met."""
    addr = {"TwnNm": "", "Ctry": "AE", "AdrLine": []}
    finding = _check_sr2026_address(addr, "Debtor")
    assert finding is not None
    assert finding["code"] == "SR2026_ADDR_MIN_GATE"
    assert "TwnNm" in finding["message"]


def test_empty_address_block_returns_no_finding():
    """Absent/empty PstlAdr block: SR2026 rule stays silent; missing-field rules handle it."""
    addr = {"TwnNm": "", "Ctry": "", "AdrLine": []}
    assert _check_sr2026_address(addr, "Debtor") is None


# ---------------------------------------------------------------------------
# sr2026_assess end-to-end
# ---------------------------------------------------------------------------

def test_unstructured_debtor_triggers_sr2026_end_to_end(unstructured_debtor_pacs008):
    """Full text -> parse -> rules pipeline: unstructured debtor address surfaces as ERROR."""
    rep = sr2026_assess(unstructured_debtor_pacs008)
    codes = [i["code"] for i in rep["issues"]]
    assert "SR2026_UNSTRUCTURED_ADDR" in codes


def test_valid_message_has_no_sr2026_address_findings(structured_pacs008):
    """Clean structured addresses on an otherwise-complete message produce zero findings."""
    rep = sr2026_assess(structured_pacs008)
    assert rep["summary"]["errors"] == 0
    assert rep["summary"]["warnings"] == 0
