# app/chroma_client.py
import os
import chromadb

API_KEY = (os.getenv("CHROMA_SERVER_AUTH") or "").strip()
TENANT  = (os.getenv("CHROMA_TENANT") or "").strip()
DB_NAME = (os.getenv("CHROMA_DATABASE") or "").strip()
COLL    = (os.getenv("CHROMA_COLLECTION") or "ccp_docs").strip()

def get_collection():
    if not API_KEY:
        raise RuntimeError("Falta CHROMA_SERVER_AUTH (api_key).")
    if not TENANT or not DB_NAME:
        raise RuntimeError("Faltan CHROMA_TENANT y/o CHROMA_DATABASE.")

    # EXACTAMENTE como el SDK del panel:
    client = chromadb.CloudClient(
        api_key=API_KEY,
        tenant=TENANT,
        database=DB_NAME,
    )
    return client.get_or_create_collection(name=COLL)
