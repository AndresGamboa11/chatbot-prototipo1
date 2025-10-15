from fastapi import FastAPI, Request
import os

app = FastAPI()

@app.get("/healthz")
async def health():
    return {"ok": True}

@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return int(challenge)
    return {"error": "Invalid token"}, 403

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Mensaje recibido:", data)
    return {"status": "received"}
