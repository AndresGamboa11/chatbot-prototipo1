# app/chroma_client.py  (ESPAÑOL)
import os, chromadb

CHROMA_HOST       = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com")
CHROMA_API_KEY    = os.getenv("CHROMA_SERVER_AUTH") or ""
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")

def get_collection():
    """
    Cliente HTTP de Chroma Cloud sin tenant/database.
    Usa solo host + Authorization header.
    """
    if not CHROMA_API_KEY:
        raise RuntimeError("Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        headers={"Authorization": f"Bearer {CHROMA_API_KEY}"},
    )
    return client.get_or_create_collection(name=CHROMA_COLLECTION)
