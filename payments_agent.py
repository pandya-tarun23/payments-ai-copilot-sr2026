from pathlib import Path

# Vector DB + LLM
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, OllamaLLM

# Your modules
from validate import validate_message, pretty_defects
from sr2026 import sr2026_assess, sr2026_pretty
from xsd_validate import validate_xml_against_xsd, get_xsd_path

from failure_analyzer import analyze_failure, pretty_failure, ai_suggestion

from autopilot import run_autopilot


BASE_DIR = Path(__file__).resolve().parent
DB_DIR = str(BASE_DIR / "chroma_payments_db")

XSD_PACS008_PATH = get_xsd_path()


def read_multiline_until_end() -> str:
    print("\nYou (paste text, then type END on a new line):")
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def main():
    # ✅ ALWAYS initialize these before the loop
    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    llm = OllamaLLM(model="llama3.1:8b", temperature=0.2)

    print("Payments Agent ready.")
    print("Commands:")
    print("  validate:      (rules-based validation)")
    print("  sr2026:        (SR2026 overlay checks)")
    print("  xsd_validate:  (XSD validation for pacs.008 XML)")
    print("Type 'exit' then END to quit.")

    while True:
        q = read_multiline_until_end()

        if not q:
            continue

        if q.lower() in {"exit", "quit"}:
            break
         
        # ---- AUTOPILOT ----
        if q.lower().startswith("autopilot:"):
            msg = q[len("autopilot:"):].strip()
            result = run_autopilot(msg, llm=llm, xsd_path=XSD_PACS008_PATH)
            print(f"\n[Autopilot detected: {result['kind']}]")
            for title, content in result["sections"]:
                print("\n=== " + title.replace("_", " ") + " ===\n")
                print(content)
            continue
    
        # ---- FAILURE ANALYSIS MODE ----
        if q.lower().startswith("failure_analysis:"):
            msg = q[len("failure_analysis:"):].strip()
            rep = analyze_failure(msg)
            print("\n" + pretty_failure(rep))

            suggestion = ai_suggestion(llm, rep)
            print("\n=== AI Suggested Actions ===\n")
            print(suggestion)

            continue

        # ---- VALIDATE MODE ----
        if q.lower().startswith("validate:"):
            msg = q[len("validate:"):].strip()
            report = validate_message(msg)
            print("\n" + pretty_defects(report))
            continue

        # ---- SR2026 MODE ----
        if q.lower().startswith("sr2026:"):
            msg = q[len("sr2026:"):].strip()
            rep = sr2026_assess(msg)
            print("\n" + sr2026_pretty(rep))
            continue

        # ---- XSD MODE ----
        if q.lower().startswith("xsd_validate:"):
            xml_msg = q[len("xsd_validate:"):].strip()

            if not XSD_PACS008_PATH.exists():
                print(
                    f"\nNo XSD schema found at {XSD_PACS008_PATH}. "
                    "Set the SR2026_XSD_PATH env var or place your own CBPR+ schema there (see README.md)."
                )
                continue

            ok, errs = validate_xml_against_xsd(xml_msg, XSD_PACS008_PATH)

            if ok:
                print("\n✅ XSD VALID (SR2026 pacs.008)")
            else:
                print("\n❌ XSD INVALID (SR2026 pacs.008)")
                for e in errs[:30]:
                    print("-", e)
                if len(errs) > 30:
                    print(f"... and {len(errs) - 30} more")
            continue

        # ---- NORMAL RAG MODE ----
        # ✅ vectordb is defined here because it was created above
        docs = vectordb.similarity_search(q, k=5)
        context = "\n\n".join([f"[Doc {i+1}]\n{d.page_content}" for i, d in enumerate(docs)])

        prompt = f"""
You are a payments-domain assistant for banking and cross-border payments.
Be accurate and conservative. If the context doesn't contain the answer, say so.

Question:
{q}

Retrieved context:
{context}

Answer clearly in bullets or short sections.
At the end include: Sources: Doc 1, Doc 2...
"""
        ans = llm.invoke(prompt)
        print("\n" + ans.strip())


if __name__ == "__main__":
    main()
