# app/chroma_client.py
"""
Cliente Chroma Cloud (Render)
Autor: Andrés Gamboa
Versión: estable con CloudClient (sin host)
"""

import os
import chromadb

# --- Configuración desde variables de entorno ---
CHROMA_AUTH = os.getenv("CHROMA_SERVER_AUTH", "").strip()
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "").strip()
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "").strip()
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs").strip()

def get_collection():
    """
    Devuelve la colección Chroma en la nube.
    Usa CloudClient con tenant y database.
    """
    if not CHROMA_AUTH:
        raise RuntimeError("❌ Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")
    if not CHROMA_TENANT or not CHROMA_DATABASE:
        raise RuntimeError("❌ Faltan CHROMA_TENANT y/o CHROMA_DATABASE.")

    client = chromadb.CloudClient(
        api_key=CHROMA_AUTH,
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
    )

    collection = client.get_or_create_collection(name=CHROMA_COLLECTION)
    return collection
