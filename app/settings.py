# app/settings.py
from pydantic import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # WhatsApp
    wa_access_token: str | None = None
    wa_phone_number_id: str | None = None
    wa_verify_token: str | None = None
    wa_api_version: str = "v21.0"

    # LLM (Groq + Gemma)
    groq_api_key: str | None = None
    groq_model: str = "gemma2-9b-it"  # ajusta si usas otro

    # Hugging Face (embeddings)
    hf_api_token: str | None = None
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Chroma (Cloud o local)
    chroma_server_host: str | None = None  # ej: https://api.trychroma.com
    chroma_server_auth: str | None = None  # token si aplica
    chroma_tenant: str | None = None
    chroma_database: str | None = None
    chroma_collection: str = "ccp_docs"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()
