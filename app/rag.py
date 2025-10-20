# app/rag.py
"""
Módulo RAG del chatbot de la Cámara de Comercio de Pamplona.
Busca información en Chroma Cloud (modo HTTP simple) y genera respuestas
usando el modelo Gemma de Groq.
"""

import os, asyncio, requests
from typing import List, Union
from app.chroma_client import get_collection  # cliente HTTP simple (sin tenant)
from groq import Groq

# ================== POLÍTICAS / PROMPT DEL ASISTENTE ==================
SYSTEM_PROMPT = """
Eres un asistente virtual de la Cámara de Comercio de Pamplona (Colombia).
Tu función es brindar información clara, precisa y actualizada sobre los servicios, trámites y actividades de la Cámara.

Responde exclusivamente sobre temas relacionados con:
- Matrícula mercantil, renovación y cancelación.
- Registro de entidades sin ánimo de lucro (ESAL).
- Certificados, tarifas y requisitos de trámites.
- Afiliaciones, capacitaciones y eventos empresariales.
- Horarios de atención, ubicación, teléfonos y canales oficiales.
- Información general institucional o de contacto.

Si el usuario pregunta por algo fuera de esos temas, responde de forma amable:
"Lo siento, solo puedo brindarte información relacionada con la Cámara de Comercio de Pamplona. ¿Te gustaría que te indique cómo contactar con un asesor?"

Usa siempre un tono cordial, natural y profesional, propio de atención al cliente.
Evita inventar información. Si no estás seguro, responde con prudencia:
"No tengo esa información exacta, te recomiendo verificarla con un asesor de la Cámara."

Tus respuestas deben ser breves (pero no tan cortas), claras y útiles para quien consulta por WhatsApp.
""".strip()

# ================== CONFIGURACIÓN ==================
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "ccp_docs")
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_HF_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_EMBED_MODEL}"
_HF_HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# LLM (Groq / Gemma)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "gemma2-9b-it")
_llm = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ================== EMBEDDINGS (Hugging Face) ==================
def hf_embed(texts: Union[str, List[str]]) -> List[List[float]]:
    """Obtiene embeddings usando la API de Hugging Face."""
    if not HF_API_TOKEN:
        raise RuntimeError("Falta la variable HF_API_TOKEN en el entorno.")

    if isinstance(texts, str):
        payload = {"inputs": [texts], "options": {"wait_for_model": True}}
    else:
        payload = {"inputs": texts, "options": {"wait_for_model": True}}

    r = requests.post(_HF_URL, headers=_HF_HEADERS, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()

    def mean_pool(v):
        if not v:
            return []
        if isinstance(v[0], (int, float)):
            return v
        if isinstance(v[0], list) and isinstance(v[0][0], (int, float)):
            seq, dim = len(v), len(v[0])
            return [sum(v[t][d] for t in range(seq)) / seq for d in range(dim)]
        if isinstance(v[0], list) and isinstance(v[0][0], list):
            return [mean_pool(x) for x in v]
        raise RuntimeError("Formato inesperado en embeddings.")
    pooled = mean_pool(data)
    return [pooled] if isinstance(pooled[0], (int, float)) else pooled

# ================== BÚSQUEDA EN CHROMA ==================
async def _search_chunks(query: str, k: int = 5) -> List[str]:
    """Busca fragmentos relevantes en Chroma Cloud."""
    col = get_collection()
    qvec = hf_embed(query)[0]
    res = col.query(query_embeddings=[qvec], n_results=k, include=["documents"])
    docs = (res.get("documents") or [[]])[0]
    return [d for d in docs if d]

# ================== PROMPT Y LLAMADA AL LLM ==================
def _build_prompt(question: str, context_docs: List[str]) -> str:
    context = "\n\n".join(context_docs[:5]) or "No hay contexto disponible."
    return f"""
{SYSTEM_PROMPT}

# Contexto
{context}

# Pregunta
{question}

# Instrucciones
- Responde en 3–6 oraciones.
- Si el tema no pertenece a la Cámara, responde con el mensaje de amabilidad.
- Si falta información confiable, usa la frase de prudencia.
"""

async def _call_llm(prompt: str) -> str:
    if not _llm:
        return "No tengo esa información exacta ahora; te recomiendo contactar un asesor."
    def _sync_call():
        completion = _llm.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        return completion.choices[0].message.content.strip()
    return await asyncio.to_thread(_sync_call)

# ================== ORQUESTACIÓN ==================
async def answer_with_rag(question: str) -> str:
    """Recupera información, construye el prompt y genera respuesta."""
    try:
        docs = await _search_chunks(question)
        if not docs:
            return "No tengo esa información exacta; te recomiendo verificarla con un asesor de la Cámara."
        prompt = _build_prompt(question, docs)
        return await _call_llm(prompt)
    except Exception as e:
        print("RAG_ERROR:", repr(e))
        return "Hubo un inconveniente procesando tu consulta. Intenta de nuevo o contacta a un asesor."
