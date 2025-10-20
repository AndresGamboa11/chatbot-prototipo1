# app/chroma_client.py  (CloudClient)
import os, chromadb

CHROMA_API_KEY    = os.getenv("CHROMA_SERVER_AUTH") or ""
CHROMA_TENANT     = (os.getenv("CHROMA_TENANT") or "").strip() or None
CHROMA_DATABASE   = (os.getenv("CHROMA_DATABASE") or "").strip() or None
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")

def get_collection():
    if not CHROMA_API_KEY:
        raise RuntimeError("Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")
    # Cliente Cloud: respeta tenant/database del panel
    client = chromadb.CloudClient(
        api_key=CHROMA_API_KEY,
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
    )
    return client.get_or_create_collection(name=CHROMA_COLLECTION)
