import os
import sys

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.insert(0, os.path.dirname(__file__))
from search import get_vector_store

load_dotenv()

PDF_PATH = os.environ["PDF_PATH"]


def split_pdf(pdf_path):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    return splitter.split_documents(documents)


def ingest_pdf(pdf_path=PDF_PATH):
    chunks = split_pdf(pdf_path)
    vector_store = get_vector_store()
    vector_store.add_documents(chunks)
    print(f"Ingestão concluída: {len(chunks)} chunks de '{pdf_path}' salvos no banco.")
    return len(chunks)


if __name__ == "__main__":
    ingest_pdf()
