# app/rag.py
import os, asyncio
from typing import List

# --- Chroma Cloud (vectores) ---
from chromadb import HttpClient
from chromadb.utils import embedding_functions

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
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST") or "https://api.trychroma.com"
CHROMA_SERVER_AUTH = os.getenv("CHROMA_SERVER_AUTH") or ""
CHROMA_TENANT       = os.getenv("CHROMA_TENANT") or ""
CHROMA_DATABASE     = os.getenv("CHROMA_DATABASE") or "bot-1"
CHROMA_COLLECTION   = os.getenv("CHROMA_COLLECTION") or "ccp_docs"
HF_EMBED_MODEL      = os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

GROQ_API_KEY        = os.getenv("GROQ_API_KEY") or ""
GROQ_MODEL          = os.getenv("GROQ_MODEL", "gemma2-9b-it")

# ====== Clientes ======
def _chroma():
    headers = {"Authorization": f"Bearer {CHROMA_SERVER_AUTH}"} if CHROMA_SERVER_AUTH else None
    client = HttpClient(
        host=CHROMA_SERVER_HOST,
        headers=headers,
        tenant=CHROMA_TENANT or None,
        database=CHROMA_DATABASE or None,
    )
    return client

_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=HF_EMBED_MODEL)
_llm = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ====== RAG ======
async def _search_chunks(query: str, k: int = 5) -> List[str]:
    client = _chroma()
    coll = client.get_or_create_collection(name=CHROMA_COLLECTION, embedding_function=_embed_fn)
    res = coll.query(query_texts=[query], n_results=k, include=["documents"])
    docs = (res.get("documents") or [[]])[0]
    return [d for d in docs if d]

def _build_prompt(question: str, context_docs: List[str]) -> str:
    context = "\n\n".join(context_docs[:5]) or "No hay contexto disponible."
    return f"""{SYSTEM_PROMPT}

# Contexto (RAG)
{context}

# Pregunta del usuario
{question}

# Instrucciones de formato
- Responde en 3–6 oraciones máximas.
- Si el tema está fuera de alcance, usa exactamente el mensaje de amabilidad indicado.
- Si falta información confiable en el contexto, dilo con la frase de prudencia indicada.
- Cuando aplique, incluye pasos breves o requisitos puntuales; si hay costos/tarifas, menciona “según tarifario vigente” si el dato exacto no está en el contexto.

# Respuesta:"""

async def _call_llm(prompt: str) -> str:
    if not _llm:
        return ("No tengo esa información exacta en este momento; "
                "te recomiendo verificarla con un asesor de la Cámara.")
    # Groq SDK es sincrónico: correr en hilo para no bloquear
    def _sync_call():
        completion = _llm.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        return completion.choices[0].message.content.strip()
    return await asyncio.to_thread(_sync_call)

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
