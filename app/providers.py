# app/providers.py
from typing import List, Dict, Any
import math
import httpx
from .settings import get_settings

# ---------- HTTP helpers ----------
async def http_post_json(url: str, headers: dict, payload: dict, timeout: float = 60.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, headers=headers, json=payload)

async def http_get(url: str, headers: dict | None = None, timeout: float = 60.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url, headers=headers or {})

# ---------- Groq (Chat Completions compatible) ----------
async def groq_chat(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 600) -> str:
    s = get_settings()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {s.groq_api_key}", "Content-Type": "application/json"}
    payload = {"model": s.groq_model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    resp = await http_post_json(url, headers, payload)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

# ---------- Hugging Face pooling util (cuando HF devuelve por tokens) ----------
def _mean_pool(v: Any) -> List[float]:
    """
    Acepta salida HF tanto [seq, dim] como [[seq, dim], ...] y devuelve vector [dim]
    """
    # Evita dependencias a numpy para mantenerlo ligero
    if not isinstance(v, list):
        raise RuntimeError("Formato inesperado de embeddings")
    # [seq, dim]
    if v and isinstance(v[0], list) and all(isinstance(x, (int, float)) for x in v[0]):
        dim = len(v[0])
        seq = len(v)
        return [sum(v[t][d] for t in range(seq)) / max(seq, 1) for d in range(dim)]
    # [[seq, dim], ...] -> promedia por batch y por seq
    if v and isinstance(v[0], list) and isinstance(v[0][0], list):
        pooled = [_mean_pool(x) for x in v]
        dim = len(pooled[0])
        n = len(pooled)
        return [sum(pooled[i][d] for i in range(n)) / max(n, 1) for d in range(dim)]
    raise RuntimeError("Formato inesperado de embeddings (2)")

# ---------- Cosine ----------
def cosine_sim(a: List[float], b: List[float]) -> float:
    s = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(y*y for y in b)) or 1.0
    return s / (na * nb)
