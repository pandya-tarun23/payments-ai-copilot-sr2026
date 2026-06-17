import pytest

STRUCTURED_PACS008 = """<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>MSG-0001</MsgId>
      <CreDtTm>2026-01-01T10:00:00</CreDtTm>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>INSTR-0001</InstrId>
        <EndToEndId>E2E-0001</EndToEndId>
      </PmtId>
      <IntrBkSttlmAmt Ccy="USD">50000.00</IntrBkSttlmAmt>
      <ChrgBr>SHAR</ChrgBr>
      <Dbtr>
        <Nm>Acme Corp</Nm>
        <PstlAdr><TwnNm>Dubai</TwnNm><Ctry>AE</Ctry></PstlAdr>
      </Dbtr>
      <Cdtr>
        <Nm>Beta GmbH</Nm>
        <PstlAdr><TwnNm>London</TwnNm><Ctry>GB</Ctry></PstlAdr>
      </Cdtr>
      <UETR>3b1e1f1e-1234-4abc-89ab-1234567890ab</UETR>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""

# Debtor has a pure unstructured address (AdrLine only); creditor stays structured.
UNSTRUCTURED_DEBTOR_PACS008 = STRUCTURED_PACS008.replace(
    "<PstlAdr><TwnNm>Dubai</TwnNm><Ctry>AE</Ctry></PstlAdr>",
    "<PstlAdr><AdrLine>P.O. Box 123, Dubai</AdrLine></PstlAdr>",
)

# SWIFT transport envelope wrapping the pacs.008 Document.
ENVELOPE_WRAPPED_PACS008 = f"""<Envelope xmlns="urn:swift:xsd:envelope">
{STRUCTURED_PACS008}
</Envelope>"""


@pytest.fixture
def structured_pacs008():
    return STRUCTURED_PACS008


@pytest.fixture
def unstructured_debtor_pacs008():
    return UNSTRUCTURED_DEBTOR_PACS008


@pytest.fixture
def envelope_wrapped_pacs008():
    return ENVELOPE_WRAPPED_PACS008
