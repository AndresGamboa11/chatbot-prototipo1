# app/chroma_client.py
import os, chromadb

CHROMA_API_KEY    = os.getenv("CHROMA_SERVER_AUTH") or os.getenv("CHROMA_API_KEY") or ""
CHROMA_TENANT     = os.getenv("CHROMA_TENANT") or None
CHROMA_DATABASE   = os.getenv("CHROMA_DATABASE") or None
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")

def _client_cloud():
    if not CHROMA_API_KEY:
        raise RuntimeError("Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")
    return chromadb.CloudClient(
        api_key=CHROMA_API_KEY,
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
    )

def get_collection():
    client = _client_cloud()
    return client.get_or_create_collection(name=CHROMA_COLLECTION)
