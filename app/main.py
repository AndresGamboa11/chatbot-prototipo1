from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import os, httpx, asyncio, uvicorn

app = FastAPI()

# --- Ruta principal
@app.get("/")
def home():
    return {"message": "Chatbot CCP online ✅"}

# --- Verificación de salud
@app.get("/healthz")
async def health():
    return {"ok": True}

# --- Verificación del webhook (Meta)
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return JSONResponse(content={"error": "Invalid token"}, status_code=403)

# --- Recepción de mensajes
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("📩 Mensaje recibido:", data)

    # Validar estructura
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            sender = message["from"]  # número del remitente
            text = message["text"]["body"]

            print(f"👤 Mensaje de {sender}: {text}")
            await send_whatsapp_message(sender, "👋 ¡Hola! Soy el Chatbot CCP. ¿En qué puedo ayudarte?")
    except Exception as e:
        print("⚠️ Error al procesar mensaje:", e)

    return {"status": "received"}

# --- Envío de mensaje
async def send_whatsapp_message(to: str, message: str):
    WHATSAPP_TOKEN = os.getenv("WA_ACCESS_TOKEN")
    PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID")

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        print("📤 Respuesta de Meta:", response.status_code, response.text)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
