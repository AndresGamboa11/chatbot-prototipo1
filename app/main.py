# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import os, json, httpx, asyncio
from app.rag import answer_with_rag  # <-- usa tu RAG

app = FastAPI()

WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or ""
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or ""
WA_API_VER = os.getenv("WA_API_VERSION", "v21.0")
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN", "verify_me")

async def send_whatsapp_text(to_number: str, body: str):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"preview_url": False, "body": body[:4096]},
            },
        )
    print("SEND RESP:", r.status_code, r.text)
    return r

@app.get("/")
def health():
    return {"ok": True}

@app.get("/webhook", response_class=PlainTextResponse)
async def verify(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return p.get("hub.challenge", "")
    return PlainTextResponse("forbidden", status_code=403)

@app.post("/webhook")
async def receive(request: Request):
    body = await request.json()
    print("WEBHOOK EVENT:", json.dumps(body, ensure_ascii=False))

    try:
        changes = body["entry"][0]["changes"][0]["value"]
        msgs = changes.get("messages", [])
        if not msgs:
            return {"status": "ok"}  # eventos de estado, etc.

        msg = msgs[0]
        from_waid = msg["from"]               # '57XXXXXXXXXX'
        user_text = msg.get("text", {}).get("body", "").strip()

        # Responder EN SEGUNDO PLANO (no bloquees el webhook)
        asyncio.create_task(process_and_reply(from_waid, user_text))
    except Exception as e:
        print("ERROR_PROCESSING_EVENT:", repr(e))

    # Siempre 200 rápido
    return {"status": "ok"}

async def process_and_reply(to_waid: str, user_text: str):
    try:
        if not user_text:
            await send_whatsapp_text(to_waid, "¿Podrías escribir tu consulta?")
            return

        # 1) (opcional) acuse de recibo rápido
        # await send_whatsapp_text(to_waid, "Recibí tu mensaje, estoy consultando...")

        # 2) Llamar a tu RAG/IA
        answer = await answer_with_rag(user_text)

        # 3) Enviar respuesta final
        await send_whatsapp_text(to_waid, answer or "No encontré datos para responder en este momento.")
    except Exception as e:
        print("ERROR_BG_TASK:", repr(e))
        try:
            await send_whatsapp_text(to_waid, "Hubo un error procesando tu consulta. Intenta de nuevo.")
        except Exception as e2:
            print("ERROR_SENDING_FAILSAFE:", repr(e2))
