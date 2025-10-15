# app/rag.py
from typing import List, Tuple
import httpx
from .settings import get_settings
from .chroma_client import get_collection
from .providers import groq_chat, _mean_pool, cosine_sim

async def hf_embed(texts: List[str]) -> List[List[float]]:
    s = get_settings()
    url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{s.hf_embed_model}"
    headers = {"Authorization": f"Bearer {s.hf_api_token}"}
    payload = {"inputs": texts, "options": {"wait_for_model": True}}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    if isinstance(texts, str):
        return [_mean_pool(data)]
    # batched
    return [_mean_pool(x) for x in data]

async def search_chroma(query: str, top_k: int = 6) -> List[Tuple[str, str, float]]:
    """
    Devuelve [(texto, doc_id, score)]
    """
    col = get_collection()
    qv = (await hf_embed([query]))[0]
    res = col.query(query_embeddings=[qv], n_results=top_k, include=["metadatas", "documents", "distances", "embeddings"])
    docs = (res.get("documents") or [[]])[0]
    metadatas = (res.get("metadatas") or [[]])[0]
    embs = (res.get("embeddings") or [[]])[0]
    # calc cosine sobre embeddings (por si distances no es cos)
    scores = [cosine_sim(qv, e) for e in embs] if embs else [1.0 - d for d in (res.get("distances") or [[]])[0]]
    out = []
    for i, txt in enumerate(docs):
        md = metadatas[i] if i < len(metadatas) else {}
        doc_id = md.get("id") or md.get("source") or f"doc_{i}"
        out.append((txt, str(doc_id), float(scores[i]) if i < len(scores) else 0.0))
    return out

def build_prompt(question: str, ctx: List[Tuple[str, str, float]]) -> list:
    citations = "\n\n".join([f"[{i+1}] ({doc_id}) {frag[:500]}" for i, (frag, doc_id, _) in enumerate(ctx)])
    system = (
        "Eres un asistente de la Cámara de Comercio de Pamplona (Colombia). "
        "Responde de forma breve, exacta y con tono cordial. "
        "Si la respuesta no está en el contexto, indica que no tienes datos y sugiere contactar a un asesor.\n"
        "Cita las fuentes como [1], [2], ... solo si son relevantes."
    )
    user = f"Pregunta: {question}\n\nContexto:\n{citations}\n\nInstrucciones: responde en español en 5-8 líneas como máximo."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]

async def answer_with_rag(question: str) -> str:
    ctx = await search_chroma(question, top_k=6)
    # opcional: rerank simple por similitud (ya usamos cosine arriba)
    ctx_top = sorted(ctx, key=lambda x: x[2], reverse=True)[:4]
    messages = build_prompt(question, ctx_top)
    try:
        answer = await groq_chat(messages, temperature=0.2, max_tokens=500)
    except Exception as e:
        # fallback minimalista
        joined = " ".join([c[0] for c in ctx_top])[:1200]
        answer = f"No pude contactar el modelo en este momento.\n\nContexto:\n{joined}"
    return answer
