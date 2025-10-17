# app/rag.py
import os, asyncio, requests
from typing import List, Union, Optional

# --- Chroma Cloud (vectores) ---
from chromadb import HttpClient

# --- LLM (Groq / Gemma) ---
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

No uses lenguaje técnico excesivo ni términos que un ciudadano promedio no entendería.
Tus respuestas deben ser breves (pero no tan cortas), claras y útiles para quien consulta por WhatsApp.
""".strip()

# ================== CONFIG RAG ==================
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST", "https://api.trychroma.com")
CHROMA_SERVER_AUTH = os.getenv("CHROMA_SERVER_AUTH", "")
CHROMA_TENANT      = os.getenv("CHROMA_TENANT", "")
CHROMA_DATABASE    = os.getenv("CHROMA_DATABASE", "bot-1")
CHROMA_COLLECTION  = os.getenv("CHROMA_COLLECTION", "ccp_docs")

# Embeddings por API (sin sentence-transformers/torch)
HF_API_TOKEN   = os.getenv("HF_API_TOKEN") or ""
HF_EMBED_MODEL = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_HF_URL        = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_EMBED_MODEL}"
_HF_HEADERS    = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}

# LLM Groq / Gemma
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or ""
GROQ_MODEL   = os.getenv("GROQ_MODEL", "gemma2-9b-it")
_llm = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ====== Embeddings (HF Inference) ======
def hf_embed(texts: Union[str, List[str]]) -> List[List[float]]:
    """
    Obtiene embeddings vía Hugging Face Inference API.
    Devuelve siempre una lista de vectores 2D: [[dim], ...]
    """
    if not HF_API_TOKEN:
        raise RuntimeError("HF_API_TOKEN no configurado en variables de entorno.")

    if isinstance(texts, str):
        payload = {"inputs": [texts], "truncate": True}
    else:
        payload = {"inputs": texts, "truncate": True}

    r = requests.post(_HF_URL, headers=_HF_HEADERS, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    # La API puede devolver [dim] para 1 texto; normalizamos a [[dim]]
    if isinstance(texts, str):
        return [data]
    return data

# ====== Cliente Chroma ======
def _chroma() -> HttpClient:
    headers = {"Authorization": f"Bearer {CHROMA_SERVER_AUTH}"} if CHROMA_SERVER_AUTH else None
    client = HttpClient(
        host=CHROMA_SERVER_HOST,
        headers=headers,
        tenant=CHROMA_TENANT or None,
        database=CHROMA_DATABASE or None,
    )
    return client

# ====== RAG: Retrieve ======
async def _search_chunks(query: str, k: int = 5) -> List[str]:
    """
    Busca en Chroma usando embeddings precomputados.
    Requiere que la colección tenga embeddings cargados en la ingesta (col.add(..., embeddings=...)).
    """
    client = _chroma()
    # ¡Importante!: NO pasar embedding_function aquí; usamos query_embeddings.
    coll = client.get_or_create_collection(name=CHROMA_COLLECTION)

    # Embedding de la consulta (HF Inference)
    qvec = hf_embed(query)[0]  # vector [dim]
    res = coll.query(
        query_embeddings=[qvec],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )

    docs = (res.get("documents") or [[]])[0]
    return [d for d in docs if d]

# ====== Prompt ======
def _build_prompt(question: str, context_docs: List[str]) -> str:
    context = "\n\n".join(context_docs[:5]) or "No hay contexto disponible."
    return f"""# Contexto (RAG)
{context}

# Pregunta del usuario
{question}

# Instrucciones de formato
- Responde en 3–6 oraciones máximas.
- Si el tema está fuera de alcance, usa exactamente el mensaje de amabilidad indicado.
- Si falta información confiable en el contexto, dilo con la frase de prudencia indicada.
- Cuando aplique, incluye pasos breves o requisitos puntuales; si hay costos/tarifas, menciona “según tarifario vigente” si el dato exacto no está en el contexto.
"""

# ====== LLM ======
async def _call_llm(prompt: str) -> str:
    if not _llm:
        return ("No tengo esa información exacta en este momento; "
                "te recomiendo verificarla con un asesor de la Cámara.")

    def _sync_call():
        completion = _llm.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=700,
        )
        return completion.choices[0].message.content.strip()

    return await asyncio.to_thread(_sync_call)

# ====== Orquestación ======
async def answer_with_rag(question: str) -> str:
    try:
        docs = await _search_chunks(question, k=5)
        if not docs:
            return ('No tengo esa información exacta en este momento; '
                    'te recomiendo verificarla con un asesor de la Cámara.')
        prompt = _build_prompt(question, docs)
        answer = await _call_llm(prompt)
        return answer
    except Exception as e:
        print("RAG_ERROR:", repr(e))
        return ("Hubo un inconveniente procesando tu consulta. "
                "Por favor, intenta de nuevo o contacta a un asesor.")
