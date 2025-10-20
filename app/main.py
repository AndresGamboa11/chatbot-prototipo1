from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os, json, httpx, asyncio
from app.rag import answer_with_rag

# --------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------------------------------
app = FastAPI()

# Montar carpeta estática
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """Página principal: muestra el index.html de static"""
    return FileResponse("static/index.html")

# Variables de entorno
WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN") or ""
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("PHONE_NUMBER_ID") or ""
WA_API_VER = os.getenv("WA_API_VERSION") or os.getenv("VERSION") or "v21.0"
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN") or "verify_me"

# --------------------------------------------------------------
# FUNCIÓN AUXILIAR: Enviar mensaje de texto
# --------------------------------------------------------------
async def send_whatsapp_text(to_number: str, body: str):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            },
        )
    print("SEND RESP:", r.status_code, r.text)
    return r

# --------------------------------------------------------------
# SALUD Y DIAGNÓSTICO
# --------------------------------------------------------------
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

# --------------------------------------------------------------
# VERIFICACIÓN WEBHOOK (GET)
# --------------------------------------------------------------
@app.get("/webhook", response_class=PlainTextResponse)
async def verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return params.get("hub.challenge", "")
    return PlainTextResponse("forbidden", status_code=403)

# --------------------------------------------------------------
# RECEPCIÓN WEBHOOK (POST)
# --------------------------------------------------------------
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

# --------------------------------------------------------------
# PROCESAR Y RESPONDER MENSAJE
# --------------------------------------------------------------
async def process_and_reply(to_waid: str, user_text: str):
    try:
        # 1) Confirmación opcional
        # await send_whatsapp_text(to_waid, "Recibí tu mensaje, estoy consultando...")

        # 2) Consultar con RAG
        answer = await answer_with_rag(user_text)

        # 3) Enviar respuesta al usuario
        final_text = answer or "No tengo esa información exacta; te recomiendo verificarla con un asesor de la Cámara."
        await send_whatsapp_text(to_waid, final_text)
    except Exception as e:
        print("ERROR_BG_TASK:", repr(e))
        await send_whatsapp_text(to_waid, "Hubo un error procesando tu consulta. Intenta de nuevo o contacta a un asesor.")

# --------------------------------------------------------------
# PRUEBA MANUAL: Enviar plantilla "hello_world"
# --------------------------------------------------------------
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

# --------------------------------------------------------------
# DIAGNÓSTICO DE CHROMA CLOUD
# --------------------------------------------------------------
@app.get("/chroma-check")
def chroma_check():
    try:
        from app.chroma_client import get_collection
        col = get_collection()
        col.query(query_texts=["ping"], n_results=1, include=[])
        return {"ok": True, "collection": col.name}
    except Exception as e:
        return {"ok": False, "error": repr(e)}

# --------------------------------------------------------------
# PROBAR RESPUESTA RAG DESDE NAVEGADOR
# --------------------------------------------------------------
@app.get("/ask")
async def ask(q: str):
    from app.rag import answer_with_rag
    ans = await answer_with_rag(q)
    return {"query": q, "answer": ans}

#ver envio 
@app.get("/chroma-env")
def chroma_env():
    import os
    return {
        "host": os.getenv("CHROMA_SERVER_HOST"),
        "auth_set": bool(os.getenv("CHROMA_SERVER_AUTH")),
        "tenant": os.getenv("CHROMA_TENANT"),
        "database": os.getenv("CHROMA_DATABASE"),
        "collection": os.getenv("CHROMA_COLLECTION"),
    }

