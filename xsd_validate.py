from pathlib import Path
from typing import List, Tuple, Optional
from lxml import etree


class LocalResolver(etree.Resolver):
    """
    Resolves xs:include/xs:import schemaLocation paths from a local base directory.
    """
    def __init__(self, base_dir: Path):
        super().__init__()
        self.base_dir = base_dir

    def resolve(self, url, pubid, context):
        # url is schemaLocation; try relative to base_dir
        candidate = (self.base_dir / url).resolve()
        if candidate.exists():
            return self.resolve_filename(str(candidate), context)
        return None


def load_schema(main_xsd_path: Path) -> etree.XMLSchema:
    if not main_xsd_path.exists():
        raise FileNotFoundError(f"XSD not found: {main_xsd_path}")

    base_dir = main_xsd_path.parent

    parser = etree.XMLParser(load_dtd=False, no_network=True, recover=False, huge_tree=True)
    parser.resolvers.add(LocalResolver(base_dir))

    xsd_doc = etree.parse(str(main_xsd_path), parser)
    return etree.XMLSchema(xsd_doc)


def validate_xml_against_xsd(xml_text: str, main_xsd_path: Path) -> Tuple[bool, List[str]]:
    schema = load_schema(main_xsd_path)

    xml_parser = etree.XMLParser(load_dtd=False, no_network=True, recover=False, huge_tree=True)
    try:
        doc = etree.fromstring(xml_text.encode("utf-8"), parser=xml_parser)
    except Exception as e:
        return False, [f"XML_PARSE_ERROR: {e}"]

    ok = schema.validate(doc)
    if ok:
        return True, []

    errors = []
    for err in schema.error_log:
        # err.line, err.column, err.message, err.type_name etc.
        errors.append(f"Line {err.line}, Col {err.column}: {err.message}")
    return False, errors


if __name__ == "__main__":
    print("Paste XML then type END:")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    xml_text = "\n".join(lines).strip()

    # Update this to your actual XSD filename:
    xsd_path = Path(__file__).resolve().parent / "rules" / "xsd" / "sr2026_pacs008" / \
        "CBPRPlus_SR2026_(Combined)_CBPRPlus-pacs_008_001_08_FIToFICustomerCreditTransfer_20260209_0820_iso15enriched.xsd"

    valid, errs = validate_xml_against_xsd(xml_text, xsd_path)
    if valid:
        print("✅ XSD VALID")
    else:
        print("❌ XSD INVALID")
        for e in errs[:50]:
            print("-", e)
        if len(errs) > 50:
            print(f"... and {len(errs)-50} more")
