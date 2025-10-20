# app/settings.py
from pydantic import BaseSettings
from functools import lru_cache
import os

def _first(*keys: str) -> str | None:
    """Devuelve el primer valor no vacío encontrado en el entorno."""
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return v.strip()
    return None

class Settings(BaseSettings):
    # WhatsApp
    wa_access_token: str | None = None
    wa_phone_number_id: str | None = None
    wa_verify_token: str | None = None
    wa_api_version: str = "v21.0"

    # LLM (Groq + Gemma)
    groq_api_key: str | None = None
    groq_model: str = "gemma2-9b-it"

    # Hugging Face (embeddings)
    hf_api_token: str | None = None
    hf_embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Chroma (Cloud o local)
    chroma_server_host: str | None = None   # ej: https://api.trychroma.com
    chroma_server_auth: str | None = None   # token si aplica
    chroma_collection: str = "ccp_docs"

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    s = Settings()

    # ====== Aliases/fallbacks por compatibilidad ======
    # WhatsApp (acepta WA_* o WHATSAPP_*)
    s.wa_access_token     = s.wa_access_token     or _first("WA_ACCESS_TOKEN", "WHATSAPP_TOKEN")
    s.wa_phone_number_id  = s.wa_phone_number_id  or _first("WA_PHONE_NUMBER_ID", "WHATSAPP_PHONE_NUMBER_ID")
    s.wa_verify_token     = s.wa_verify_token     or _first("WA_VERIFY_TOKEN", "WHATSAPP_VERIFY_TOKEN")

    # Groq
    s.groq_api_key        = s.groq_api_key        or _first("GROQ_API_KEY")
    s.groq_model          = s.groq_model          or _first("GROQ_MODEL") or "gemma2-9b-it"

    # Hugging Face
    s.hf_api_token        = s.hf_api_token        or _first("HF_API_TOKEN")
    s.hf_embed_model      = s.hf_embed_model      or _first("HF_EMBED_MODEL") or "sentence-transformers/all-MiniLM-L6-v2"

    # Chroma (acepta CHROMA_SERVER_AUTH o CHROMA_API_KEY)
    s.chroma_server_host  = s.chroma_server_host  or _first("CHROMA_SERVER_HOST")
    s.chroma_server_auth  = s.chroma_server_auth  or _first("CHROMA_SERVER_AUTH", "CHROMA_API_KEY")
    s.chroma_collection   = s.chroma_collection   or _first("CHROMA_COLLECTION") or "ccp_docs"

    return s
