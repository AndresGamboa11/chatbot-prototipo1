from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# === Configuración de variables ===
VERIFY_TOKEN = (os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()

# === Servir carpeta estática ===
app.mount("/static", StaticFiles(directory="static"), name="static")

# === Página principal ===
@app.get("/")
async def root():
    return FileResponse("static/index.html")

# === Healthcheck (Render lo usa para saber si está viva la app) ===
@app.get("/healthz")
async def healthz():
    return {"ok": True}

# === Endpoint para depurar token ===
@app.get("/debug-token")
async def debug_token():
    masked = "*"*(len(VERIFY_TOKEN)-2) + VERIFY_TOKEN[-2:] if VERIFY_TOKEN else ""
    return JSONResponse({"env_token_masked": masked, "len": len(VERIFY_TOKEN)})

# === Webhook para WhatsApp Cloud API ===
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = (request.query_params.get("hub.verify_token") or "").strip()
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(challenge, status_code=200)
    return JSONResponse({"error": "Invalid token"}, status_code=403)

@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    print("📩 webhook body:", body)
    return {"status": "ok"}
