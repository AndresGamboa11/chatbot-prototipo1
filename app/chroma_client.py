# app/chroma_client.py
import os, chromadb

API_KEY = (os.getenv("CHROMA_SERVER_AUTH") or "").strip()
TENANT  = (os.getenv("CHROMA_TENANT") or "").strip()
DB_NAME = (os.getenv("CHROMA_DATABASE") or "").strip()
COLL    = (os.getenv("CHROMA_COLLECTION") or "ccp_docs").strip()
HOST    = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com").strip()

def get_collection():
    if not API_KEY:
        raise RuntimeError("Falta CHROMA_SERVER_AUTH (api_key).")
    if not TENANT or not DB_NAME:
        raise RuntimeError("Faltan CHROMA_TENANT y/o CHROMA_DATABASE.")

    client = chromadb.CloudClient(
        api_key=API_KEY,
        tenant=TENANT,
        database=DB_NAME,
        host=HOST,  # por si tu versión lo soporta; en 0.5.5 no molesta
    )
    return client.get_or_create_collection(name=COLL)
