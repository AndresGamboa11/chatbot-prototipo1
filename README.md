# ccp-whatsapp-rag-cloud

Webhook de WhatsApp (FastAPI) + RAG con **Chroma Cloud** + **re-rank** + LLM en **Groq** y embeddings mediante **Hugging Face Inference API**. Listo para desplegar en **Deta Space**.

## Estructura
```
ccp-whatsapp-rag-cloud/
├─ app/
│  ├─ main.py          # FastAPI: verificación webhook + recepción mensajes
│  ├─ rag.py           # retrieve → re-rank → prompt → LLM (Gemma/Groq)
│  ├─ providers.py     # clientes HTTP: Groq, Hugging Face, WhatsApp
│  ├─ whatsapp.py      # envío de mensajes vía Graph API
│  ├─ chroma_client.py # cliente Chroma Cloud
│  └─ settings.py      # configuración (.env)
├─ ingest/
│  └─ ingest_ccp.py    # carga documentos CCP → embeddings HF → Chroma
├─ requirements.txt
├─ Spacefile           # despliegue en Deta Space
├─ .env.example
└─ README.md
```

## Despliegue local (Docker opcional)
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```
o con Docker:
```bash
docker build -t ccp-whatsapp-rag-cloud .
docker run --env-file .env -p 8080:8080 ccp-whatsapp-rag-cloud
```

## Deta Space
1. Crea variables de entorno (ver `.env.example`) en tu proyecto Space.
2. Space ejecuta `scripts.build` y `scripts.start` definidos en `Spacefile`.
3. Expón la URL pública y configúrala en **Meta Developers**:
   - Verificación (GET): `https://TU_URL/webhook?hub.mode=subscribe&hub.verify_token=...`
   - Recepción (POST): `https://TU_URL/webhook`

## Ingesta (Chroma Cloud)
Archivo JSONL (una línea por documento):
```json
{"id":"faq-001","text":"¿Cuál es el horario de atención?","metadata":{"source":"web"}}
```
Sube a Chroma (usa HF para embeddings):
```bash
python -m ingest.ingest_ccp --file data/ccp_faq.jsonl
```

## Notas
- Ajusta `GROQ_MODEL` (por ejemplo, `llama-3.1-8b-instant` o el modelo Gemma disponible en Groq).
- Si prefieres embeddings locales, reemplaza `HuggingFaceEmbeddings` por `sentence-transformers`.
# chatbot-prototipo1
