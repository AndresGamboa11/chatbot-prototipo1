# app/chroma_client.py
"""
Cliente Chroma Cloud (HttpClient con headers de tenant/database opcionales).
Si CHROMA_TENANT y/o CHROMA_DATABASE están definidos, se envían en los headers:
- X-Chroma-Tenant
- X-Chroma-Database
Esto evita el uso de 'default_tenant' en cuentas que exigen multi-tenant.
"""

import os
import chromadb

CHROMA_HOST       = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com")
CHROMA_AUTH       = os.getenv("CHROMA_SERVER_AUTH", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")
CHROMA_TENANT     = (os.getenv("CHROMA_TENANT") or "").strip()
CHROMA_DATABASE   = (os.getenv("CHROMA_DATABASE") or "").strip()

def get_collection():
    if not CHROMA_AUTH:
        raise RuntimeError("❌ Falta CHROMA_SERVER_AUTH (API key de Chroma Cloud).")

    headers = {"Authorization": f"Bearer {CHROMA_AUTH}"}
    # Si tu cuenta requiere tenant/database, añade estos headers:
    if CHROMA_TENANT:
        headers["X-Chroma-Tenant"] = CHROMA_TENANT
    if CHROMA_DATABASE:
        headers["X-Chroma-Database"] = CHROMA_DATABASE

    client = chromadb.HttpClient(
        host=CHROMA_HOST,
        headers=headers,
    )

    return client.get_or_create_collection(name=CHROMA_COLLECTION)
