# app/chroma_client.py
import chromadb
from .settings import get_settings

import os
import chromadb

CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST")
CHROMA_SERVER_AUTH = os.getenv("CHROMA_SERVER_AUTH")
CHROMA_TENANT = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "bot-1")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")

client = chromadb.HttpClient(
    host=CHROMA_SERVER_HOST,
    headers={"Authorization": f"Bearer {CHROMA_SERVER_AUTH}"},
    tenant=CHROMA_TENANT,
    database=CHROMA_DATABASE,
)


def get_collection():
    return client.get_or_create_collection(name=CHROMA_COLLECTION)

_DEFAULT_METADATA = {"hnsw:space": "cosine"}

def _http_client():
    s = get_settings()
    if not s.chroma_server_host:
        return None
    return chromadb.HttpClient(
        host=s.chroma_server_host,
        settings=chromadb.config.Settings(
            anonymized_telemetry=False,
            allow_reset=True,
            chroma_client_auth_provider="token" if s.chroma_server_auth else None,
            chroma_client_auth_credentials=s.chroma_server_auth or None,
        ),
        tenant=s.chroma_tenant,
        database=s.chroma_database,
    )

def _local_client():
    return chromadb.PersistentClient(path=".chroma")

def _client():
    return _http_client() or _local_client()

def get_collection(name: str = "ccp_docs"):
    # Ajusta la ruta exacta a la que subiste:
    store_path = Path("/mnt/data/vectorstore/vectorstore/ccp").resolve()
    client = chromadb.PersistentClient(path=str(store_path))
    return client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
