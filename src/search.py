import os

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
COLLECTION_NAME = os.environ["PGVECTOR_COLLECTION"]
EMBEDDING_MODEL = os.environ["GOOGLE_EMBEDDING_MODEL"]


def get_vector_store():
    embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
    return PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )


def search_similar_chunks(query, k=10):
    vector_store = get_vector_store()
    return vector_store.similarity_search_with_score(query, k=k)
