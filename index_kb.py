#index_kb.py
import os
from glob import glob

from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
#from langchain_community.vectorstores import Chroma
#from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_ollama import OllamaEmbeddings
#from langchain_ollama import Chroma

KB_DIR = "payments_kb"
DB_DIR = "chroma_payments_db"

def load_documents():
    docs = []
    # Load .md/.txt
    for path in glob(os.path.join(KB_DIR, "**/*.md"), recursive=True) + \
                glob(os.path.join(KB_DIR, "**/*.txt"), recursive=True):
        docs.extend(TextLoader(path, encoding="utf-8").load())

    # Load PDFs
    for path in glob(os.path.join(KB_DIR, "**/*.pdf"), recursive=True):
        docs.extend(PyPDFLoader(path).load())

    return docs

def main():
    docs = load_documents()
    if not docs:
        raise RuntimeError(f"No docs found under {KB_DIR}. Add .md/.txt/.pdf first.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    embeddings = OllamaEmbeddings(model="nomic-embed-text")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_DIR
    )
    vectordb.persist()
    print(f"Indexed {len(chunks)} chunks into {DB_DIR}")

if __name__ == "__main__":
    main()
