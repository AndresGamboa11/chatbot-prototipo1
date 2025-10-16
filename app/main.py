from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import json
import httpx

app = FastAPI()

# Montar carpeta estática (sirve index.html, imágenes, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Página principal → muestra el index.html
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("static/index.html")


# Endpoint de salud (Render lo usa)
@app.get("/healthz", include_in_schema=False)
async def healthz():
    return JSONResponse({"ok": True})


# Configuración WhatsApp (usa variables de entorno)
WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN")
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WA_API_VER = os.getenv("WA_API_VERSION", "v21.0")


# Envío de mensaje a WhatsApp
async def send_whatsapp_text(to_number: str, body: str) -> dict:
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"📤 WA status={r.status_code} body={r.text[:200]}")
        return {"status": r.status_code, "text": r.text}


# Webhook (verificación + recepción)
@app.get("/webhook", include_in_schema=False)
async def verify(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == os.getenv("WA_VERIFY_TOKEN"):
        return JSONResponse(content=params.get("hub.challenge"))
    return JSONResponse(content="Forbidden", status_code=403)


@app.post("/webhook", include_in_schema=False)
async def webhook(request: Request):
    try:
        body = await request.json()
    except json.JSONDecodeError:
        print("⚠️ cuerpo vacío o no JSON")
        return JSONResponse({"status": "ok"})

    print("📩 payload:", body)
    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for m in value.get("messages", []):
                    user = m.get("from")
                    text = (m.get("text") or {}).get("body", "")
                    if user and text:
                        await send_whatsapp_text(user, f"Recibí tu mensaje: {text}")
    except Exception as e:
        print("❌ error webhook:", e)
    return JSONResponse({"status": "ok"})
