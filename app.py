import streamlit as st
from pathlib import Path

from validate import validate_message, pretty_defects
from sr2026 import sr2026_assess, sr2026_pretty
from xsd_validate import validate_xml_against_xsd, get_xsd_path
from failure_analyzer import analyze_failure, pretty_failure, ai_suggestion

from langchain_ollama import OllamaLLM

from autopilot import run_autopilot

# Initialize LLM once
llm = OllamaLLM(model="llama3.1:8b", temperature=0.2)

BASE_DIR = Path(__file__).resolve().parent
XSD_PATH = get_xsd_path()


st.set_page_config(page_title="Payments AI Copilot", layout="wide")
st.title("🏦 Payments AI Copilot — SR2026 Assistant")

mode = st.radio(
    "Select Mode",
    [
        "Autopilot (Recommended)",
        "Validate",
        "SR2026 Assessment",
        "XSD Validation",
        "Failure Analysis + AI Suggestions"
    ],
    horizontal=True
)

text = st.text_area("Paste message / incident", height=280)

if mode == "Autopilot (Recommended)":
    result = run_autopilot(text, llm=llm, xsd_path=XSD_PATH)

    st.subheader(f"Autopilot detected: {result['kind']}")

    for title, content in result["sections"]:
        st.markdown(f"### {title.replace('_',' ')}")
        st.code(content, language="text")

    st.stop()

if st.button("Run", type="primary"):

    if not text.strip():
        st.warning("Paste input first")
        st.stop()

    # ---- VALIDATION ----
    if mode == "Validate":
        rep = validate_message(text)
        st.code(pretty_defects(rep), language="text")

    # ---- SR2026 ----
    elif mode == "SR2026 Assessment":
        rep = sr2026_assess(text)
        st.code(sr2026_pretty(rep), language="text")

    # ---- XSD ----
    elif mode == "XSD Validation":
        if not XSD_PATH.exists():
            st.warning(
                f"No XSD schema found at {XSD_PATH}. "
                "Set the SR2026_XSD_PATH env var or place your own CBPR+ schema there (see README.md)."
            )
        else:
            ok, errs = validate_xml_against_xsd(text, XSD_PATH)
            if ok:
                st.success("✅ XSD VALID")
            else:
                st.error("❌ XSD INVALID")
                st.code("\n".join(errs[:50]), language="text")

    # ---- FAILURE + AI ----
    else:
        rep = analyze_failure(text)

        st.subheader("Failure Analysis")
        st.code(pretty_failure(rep), language="text")

        st.subheader("AI Suggested Actions")
        suggestion = ai_suggestion(llm, rep)
        st.markdown(suggestion)

