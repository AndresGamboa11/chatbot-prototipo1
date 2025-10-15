# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import os

app = FastAPI()

VERIFY_TOKEN = (os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = (request.query_params.get("hub.verify_token") or "").strip()
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        # devolver el challenge en TEXTO PLANO
        return PlainTextResponse(challenge, status_code=200)
    return JSONResponse({"error": "Token inválido"}, status_code=403)

# (puedes borrar este endpoint tras probar)
@app.get("/debug-token")
async def debug_token():
    # Muestra solo los últimos 2 dígitos; NO expone el token completo
    masked = VERIFY_TOKEN[:-2].replace(VERIFY_TOKEN[:-2], "*"*max(len(VERIFY_TOKEN)-2, 0)) + VERIFY_TOKEN[-2:]
    return {"env_token_masked": masked, "len": len(VERIFY_TOKEN)}
