# app/chroma_client.py
"""
Cliente Chroma Cloud (HttpClient) con tenant/database explícitos.
Envía tenant/database tanto como argumentos del cliente como en headers
para cubrir cualquier versión del SDK/servidor.
"""

import os
import chromadb

CHROMA_HOST       = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com")
CHROMA_AUTH       = os.getenv("CHROMA_SERVER_AUTH", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")
CHROMA_TENANT     = (os.getenv("CHROMA_TENANT") or "").strip() or None
CHROMA_DATABASE   = (os.getenv("CHROMA_DATABASE") or "").strip() or None


def get_collection():
    if not CHROMA_AUTH:
        raise RuntimeError("❌ Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")

    # Autorización + (opcional) nombres de tenant/database como headers
    headers = {"Authorization": f"Bearer {CHROMA_AUTH}"}
    if CHROMA_TENANT:
        headers["X-Chroma-Tenant"] = CHROMA_TENANT
    if CHROMA_DATABASE:
        headers["X-Chroma-Database"] = CHROMA_DATABASE

    # 🚧 IMPORTANTE: pasar tenant/database como argumentos del cliente
    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        headers=headers,
        tenant=CHROMA_TENANT,
        database=CHROMA_DATABASE,
    )

    return client.get_or_create_collection(name=CHROMA_COLLECTION)
