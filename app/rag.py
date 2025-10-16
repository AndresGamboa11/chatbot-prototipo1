from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import os, json, httpx
from app.rag import answer_with_rag  # si tu función existe

# --- estático e index ---
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
async def root():
    return FileResponse("static/index.html")
app = FastAPI()

WA_TOKEN = os.getenv("WA_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN")
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WA_API_VER = os.getenv("WA_API_VERSION", "v21.0")

# --------------------------------------------------------------
# FUNCIONES DE APOYO
# --------------------------------------------------------------

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


async def wa_mark_read(message_id: str):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(url, headers=headers, json=payload)

async def wa_typing(to_number: str, state: str = "composing"):
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "typing", "typing": {"state": state}}
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(url, headers=headers, json=payload)

# --------------------------------------------------------------
# ENDPOINT PRINCIPAL
# --------------------------------------------------------------

@app.post("/webhook")
async def webhook(req: Request):
    raw = await req.body()
    if not raw:
        return {"status": "ok"}

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        print("⚠️ POST no-JSON recibido")
        return {"status": "ok"}

    print("📩 payload:", body)

    try:
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for msg in value.get("messages", []):
                    user = msg.get("from")
                    msg_id = msg.get("id")
                    text = (msg.get("text") or {}).get("body", "").strip()

                    if user and text:
                        await wa_mark_read(msg_id)
                        await wa_typing(user, "composing")

                        try:
                            # 🔹 Lógica de respuesta (usa RAG o simple eco)
                            reply = await answer_with_rag(text)
                        except Exception as e:
                            print("❌ Error en RAG:", e)
                            reply = f"Recibí tu mensaje: {text}"

                        await wa_typing(user, "paused")
                        await send_whatsapp_text(user, reply)

    except Exception as e:
        print("❌ Error en webhook:", e)

    return JSONResponse({"status": "ok"})
