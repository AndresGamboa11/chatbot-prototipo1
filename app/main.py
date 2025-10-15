from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import os
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Chatbot CCP online ✅"}

@app.get("/healthz")
async def health():
    return {"ok": True}

# ✅ Verificación Webhook (GET)
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("WHATSAPP_VERIFY_TOKEN")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        # WhatsApp exige devolver el challenge como texto plano
        return PlainTextResponse(content=challenge, status_code=200)
    return JSONResponse(content={"error": "Invalid token"}, status_code=403)

# ✅ Recepción de mensajes (POST)
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Mensaje recibido:", data)
    return {"status": "received"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
