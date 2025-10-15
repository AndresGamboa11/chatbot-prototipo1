# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# 1) Servir archivos estáticos (carpeta en la raíz del proyecto)
#    Si tu carpeta está dentro de app (app/static), cambia directory="app/static"
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2) Página principal: devuelve tu index.html
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# 3) Healthcheck para Render
@app.get("/healthz")
async def healthz():
    return {"ok": True}

# 4) Webhook de WhatsApp (NO HTML aquí)
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN")

# Verificación (GET)
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == (VERIFY_TOKEN or "") and challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("forbidden", status_code=403)

# Recepción de mensajes (POST)
@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    print("📩 webhook body:", body)
    # aquí llamas a tu lógica de RAG y send_whatsapp_text(...)
    return {"status": "ok"}
