from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# === CONFIG ===
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN")

# === 1. Servir carpeta estática ===
# Si tu carpeta "static" está en la raíz del proyecto:
app.mount("/static", StaticFiles(directory="static"), name="static")

# === 2. Página principal ===
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# === 3. Healthcheck para Render ===
@app.get("/healthz")
async def healthz():
    return {"ok": True}

# === 4. Webhook de WhatsApp ===
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    else:
        return PlainTextResponse("forbidden", status_code=403)

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 webhook body:", data)
    return {"status": "ok"}
