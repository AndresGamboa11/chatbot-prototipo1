# app/chroma_client.py  (ESPAÑOL)
"""
Cliente Chroma Cloud (modo simple para Render)
Autor: Andrés Gamboa
Descripción:
Conecta a Chroma Cloud sin necesidad de tenant ni database, usando solo la API key.
"""

import os
import chromadb

# --- Configuración desde variables de entorno ---
CHROMA_HOST = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com")
CHROMA_AUTH = os.getenv("CHROMA_SERVER_AUTH", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")


def get_collection():
    """
    Devuelve la colección de Chroma configurada en la nube.
    Si no existe, la crea automáticamente.
    """
    if not CHROMA_AUTH:
        raise RuntimeError("❌ Falta la variable CHROMA_SERVER_AUTH (API key de Chroma Cloud).")

    # Cliente HTTP (NO usar CloudClient)
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        headers={"Authorization": f"Bearer {CHROMA_AUTH}"}
    )

    collection = client.get_or_create_collection(name=CHROMA_COLLECTION)
    return collection
