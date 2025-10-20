# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os, json, httpx, asyncio
import chromadb

from app.rag import answer_with_rag
from app.chroma_client import get_collection

app = FastAPI()

# Archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Página principal
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# Variables WhatsApp
WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN") or ""
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("PHONE_NUMBER_ID") or ""
WA_API_VER = os.getenv("WA_API_VERSION") or os.getenv("VERSION") or "v21.0"
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN") or "verify_me"

# ---------- Utilidad: enviar texto por WhatsApp ----------
async def send_whatsapp_text(to_number: str, body: str):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {WA_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            },
        )
    print("SEND RESP:", r.status_code, r.text)
    return r

# ---------- Salud ----------
@app.get("/healthz")
def healthz():
    return {"ok": True, "servicio": "CCP WhatsApp RAG", "webhook": "/webhook"}

@app.get("/env-check")
def env_check():
    return {
        "WA_ACCESS_TOKEN_set": bool(WA_TOKEN),
        "WA_PHONE_NUMBER_ID_set": bool(WA_PHONE_ID),
        "WA_API_VERSION": WA_API_VER,
        "VERIFY_TOKEN_set": bool(VERIFY_TOKEN),
    }

# ---------- Webhook GET (verificación) ----------
@app.get("/webhook", response_class=PlainTextResponse)
async def verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return params.get("hub.challenge", "")
    return PlainTextResponse("forbidden", status_code=403)

# ---------- Webhook POST (mensajes) ----------
@app.post("/webhook")
async def receive(request: Request):
    body = await request.json()
    print("WEBHOOK EVENT:", json.dumps(body, ensure_ascii=False))
    try:
        changes = body["entry"][0]["changes"][0]["value"]
        msgs = changes.get("messages", [])
        if not msgs:
            return {"status": "ok"}
        msg = msgs[0]
        from_waid = msg["from"]
        user_text = msg.get("text", {}).get("body", "").strip()
        asyncio.create_task(process_and_reply(from_waid, user_text))
    except Exception as e:
        print("ERROR_PROCESSING_EVENT:", repr(e))
    return {"status": "ok"}

async def process_and_reply(to_waid: str, user_text: str):
    try:
        answer = await answer_with_rag(user_text)
        final_text = answer or "No tengo esa información exacta; te recomiendo verificarla con un asesor de la Cámara."
        await send_whatsapp_text(to_waid, final_text)
    except Exception as e:
        print("ERROR_BG_TASK:", repr(e))
        await send_whatsapp_text(
            to_waid,
            "Hubo un error procesando tu consulta. Intenta de nuevo o contacta a un asesor.",
        )

# ---------- Envío manual de plantilla ----------
@app.get("/send-test")
async def send_test(to: str):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, headers={"Authorization": f"Bearer {WA_TOKEN}"}, json=payload)
    try:
        return JSONResponse({"status": r.status_code, "json": r.json()})
    except Exception:
        return JSONResponse({"status": r.status_code, "text": r.text})

# ---------- Diagnóstico Chroma ----------
@app.get("/chroma-env")
def chroma_env():
    return {
        "host": os.getenv("CHROMA_SERVER_HOST"),
        "auth_set": bool(os.getenv("CHROMA_SERVER_AUTH")),
        "collection": os.getenv("CHROMA_COLLECTION"),
        "tenant": os.getenv("CHROMA_TENANT"),
        "database": os.getenv("CHROMA_DATABASE"),
    }

@app.get("/chroma-check")
def chroma_check():
    try:
        col = get_collection()
        # operación segura: contar o peek (sin embeddings)
        try:
            count = col.count()
        except Exception:
            try:
                peek = col.peek() or {}
                count = len(peek.get("ids", []))
            except Exception:
                count = None
        return {"ok": True, "collection": col.name, "count": count}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

@app.get("/chroma-version")
def chroma_version():
    return {
        "chromadb_version": getattr(chromadb, "__version__", "unknown"),
        "host": os.getenv("CHROMA_SERVER_HOST"),
        "tenant": os.getenv("CHROMA_TENANT"),
        "database": os.getenv("CHROMA_DATABASE"),
        "api_key_prefix": (os.getenv("CHROMA_SERVER_AUTH") or "")[:5],
        "api_key_len": len(os.getenv("CHROMA_SERVER_AUTH") or ""),
    }

@app.get("/chroma-debug")
def chroma_debug():
    try:
        col = get_collection()
        client_type = str(type(col._client))
        try:
            names = [c.name for c in col._client.list_collections()]
        except Exception as e2:
            names = f"list_collections_error: {repr(e2)}"
        return {"ok": True, "client_type": client_type, "collections": names}
    except Exception as e:
        return {"ok": False, "e
