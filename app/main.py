# app/main.py (fragmento clave)

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os, httpx

app = FastAPI()

# --- estático e index ---
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/healthz")
async def healthz():
    return {"ok": True}

# --- WhatsApp config ---
VERIFY_TOKEN = (os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()
WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN")
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WA_API_VER = os.getenv("WA_API_VERSION", "v21.0")

# Verificación (GET)
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = (request.query_params.get("hub.verify_token") or "").strip()
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("forbidden", status_code=403)

# Enviar texto por WhatsApp
async def send_whatsapp_text(to_number: str, body: str) -> dict:
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        try:
            r.raise_for_status()
            return r.json()
        except Exception:
            return {"status": r.status_code, "text": r.text[:300]}

# Webhook (POST): lee el mensaje y responde
@app.post("/webhook")
async def webhook(req: Request):
    body = await req.json()
    print("📩 payload:", body)

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for m in messages:
                    from_id = m.get("from")                    # número del usuario
                    msg_type = m.get("type")

                    # soporta texto, botón e interactivo
                    if msg_type == "text":
                        text = (m.get("text") or {}).get("body", "").strip()
                    elif msg_type == "button":
                        text = (m.get("button") or {}).get("text", "").strip()
                    elif msg_type == "interactive":
                        text = (m.get("interactive") or {}).get("button_reply", {}).get("title", "").strip()
                    else:
                        text = ""

                    if from_id and text:
                        # aquí puedes llamar a tu RAG; por ahora respondemos eco
                        reply = f"Recibí: {text}"
                        out = await send_whatsapp_text(from_id, reply)
                        print("📤 respuesta WA:", out)
    except Exception as e:
        print("❌ error webhook:", e)

    return JSONResponse({"status": "ok"})
