# app/rag.py
import os, asyncio
from typing import List

# --- Embeddings / Chroma ---
from chromadb import HttpClient
from chromadb.utils import embedding_functions

# --- LLM (Groq/Gemma) ---
from groq import Groq

CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST") or "https://api.trychroma.com"
CHROMA_SERVER_AUTH = os.getenv("CHROMA_SERVER_AUTH") or ""
CHROMA_TENANT       = os.getenv("CHROMA_TENANT") or ""
CHROMA_DATABASE     = os.getenv("CHROMA_DATABASE") or "bot-1"
CHROMA_COLLECTION   = os.getenv("CHROMA_COLLECTION") or "ccp_docs"
HF_EMBED_MODEL      = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

GROQ_API_KEY        = os.getenv("GROQ_API_KEY") or ""
GROQ_MODEL          = os.getenv("GROQ_MODEL", "gemma2-9b-it")

# Cliente Chroma Cloud
def _chroma():
    client = HttpClient(
        host=CHROMA_SERVER_HOST,
        headers={"Authorization": f"Bearer {CHROMA_SERVER_AUTH}"} if CHROMA_SERVER_AUTH else None,
        tenant=CHROMA_TENANT or None,
        database=CHROMA_DATABASE or None,
    )
    return client

# Embeddings HF
_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=HF_EMBED_MODEL)

# Cliente Groq
_llm = Groq(api_key=GROQ_API_KEY)

async def _search_chunks(query: str, k: int = 5) -> List[str]:
    client = _chroma()
    coll = client.get_or_create_collection(name=CHROMA_COLLECTION, embedding_function=_embed_fn)
    res = coll.query(query_texts=[query], n_results=k, include=["documents"])
    docs = (res.get("documents") or [[]])[0]
    return [d for d in docs if d]

def _build_prompt(question: str, context_docs: List[str]) -> str:
    context = "\n\n".join(context_docs[:5]) or "No hay contexto disponible."
    return f"""Eres un asistente para la Cámara de Comercio de Pamplona (Colombia).
Responde en español de forma clara y breve, citando los puntos clave del contexto si aplican.
Si la información no aparece en el contexto, dilo y sugiere cómo obtenerla.

# Contexto (RAG)
{context}

# Pregunta del usuario
{question}

# Respuesta:"""

async def _call_llm(prompt: str) -> str:
    # Groq Python SDK es sincrónico; ejecútalo en hilo
    def _sync():
        completion = _llm.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        return completion.choices[0].message.content.strip()
    return await asyncio.to_thread(_sync)

async def answer_with_rag(question: str) -> str:
    try:
        docs = await _search_chunks(question, k=5)
        prompt = _build_prompt(question, docs)
        answer = await _call_llm(prompt)
        return answer
    except Exception as e:
        print("RAG_ERROR:", repr(e))
        return "No pude generar una respuesta con la base de conocimiento por ahora."
