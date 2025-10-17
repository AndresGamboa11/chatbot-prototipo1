# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse
import os, json, httpx, asyncio
from app.rag import answer_with_rag  # <-- usa tu RAG/IA

app = FastAPI()

# ---------- VARIABLES DE ENTORNO ----------
WA_TOKEN = (
    os.getenv("WA_ACCESS_TOKEN")
    or os.getenv("ACCESS_TOKEN")
    or ""  # si queda vacío, /env-check lo mostrará
)
WA_PHONE_ID = os.getenv("WA_PHONE_NUMBER_ID") or os.getenv("PHONE_NUMBER_ID") or ""
WA_API_VER = os.getenv("WA_API_VERSION") or os.getenv("VERSION") or "v21.0"
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN") or os.getenv("VERIFY_TOKEN") or "verify_me"

# ---------- UTIL ----------
async def send_whatsapp_text(to_number: str, body: str):
    """Envía un texto simple por WhatsApp."""
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
    if r.status_code == 401:
        print("HINT: 401 → Token inválido/expirado. Renueva WA_ACCESS_TOKEN en Render.")
    if r.status_code == 400 and "phone number" in (r.text or "").lower():
        print("HINT: PHONE_NUMBER_ID incorrecto o no pertenece a tu app/WABA.")
    return r

# Alcance permitido (filtro rápido opcional)
IN_SCOPE = [
    "matrícula", "matricula", "renovación", "renovacion", "cancelación", "cancelacion",
    "esal", "entidad sin ánimo de lucro", "entidades sin ánimo de lucro",
    "certificado", "certificados", "tarifa", "tarifas", "requisitos", "trámite", "tramite", "trámites", "tramites",
    "afiliación", "afiliaciones", "capacitaciones", "eventos",
    "horario", "horarios", "ubicación", "ubicacion", "telefono", "teléfono", "contacto",
    "cámara de comercio de pamplona", "camara de comercio de pamplona", "cc pamplona", "cámara pamplona", "camara pamplona"
]

def _out_of_scope(user_text: str) -> bool:
    t = (user_text or "").lower()
    return not any(k in t for k in IN_SCOPE)

# ---------- SALUD Y DIAGNÓSTICO ----------
@app.get("/")
def root():
    return {"ok": True}

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/env-check")
def env_check():
    # No expone secretos; solo presencia/longitud
    return {
        "WA_ACCESS_TOKEN_set": bool(WA_TOKEN),
        "WA_ACCESS_TOKEN_len": len(WA_TOKEN or ""),
        "WA_PHONE_NUMBER_ID_set": bool(WA_PHONE_ID),
        "WA_API_VERSION": WA_API_VER,
        "VERIFY_TOKEN_set": bool(VERIFY_TOKEN),
    }

# ---------- VERIFICACIÓN WEBHOOK (GET) ----------
@app.get("/webhook", response_class=PlainTextResponse)
async def verify(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return p.get("hub.challenge", "")
    return PlainTextResponse("forbidden", status_code=403)

# ---------- RECEPCIÓN WEBHOOK (POST) ----------
@app.post("/webhook")
async def receive(request: Request):
    body = await request.json()
    print("WEBHOOK EVENT:", json.dumps(body, ensure_ascii=False))

    try:
        changes = body["entry"][0]["changes"][0]["value"]
        msgs = changes.get("messages", [])
        if not msgs:
            return {"status": "ok"}  # eventos sin mensaje (ack, estados, etc.)

        msg = msgs[0]
        from_waid = msg["from"]
        user_text = msg.get("text", {}).get("body", "").strip()

        # Procesar en segundo plano (no bloquear el 200 del webhook)
        asyncio.create_task(process_and_reply(from_waid, user_text))
    except Exception as e:
        print("ERROR_PROCESSING_EVENT:", repr(e))

    # SIEMPRE 200 rápido
    return {"status": "ok"}

async def process_and_reply(to_waid: str, user_text: str):
    """Procesa la consulta, aplica reglas de alcance y responde con RAG/IA."""
    try:
        # 1) Filtro rápido de alcance (tus políticas)
        if _out_of_scope(user_text):
            msg = ("Lo siento, solo puedo brindarte información relacionada con la Cámara de Comercio de Pamplona. "
                   "¿Te gustaría que te indique cómo contactar con un asesor?")
            await send_whatsapp_text(to_waid, msg)
            return

        # 2) Opción: acuse de recibo (descomenta si lo deseas)
        # await send_whatsapp_text(to_waid, "Recibí tu mensaje, estoy consultando…")

        # 3) Llamar RAG/IA
        answer = await answer_with_rag(user_text)

        # 4) Responder al usuario
        final_text = (answer or
                      "No tengo esa información exacta; te recomiendo verificarla con un asesor de la Cámara.")
        await send_whatsapp_text(to_waid, final_text)
    except Exception as e:
        print("ERROR_BG_TASK:", repr(e))
        try:
            await send_whatsapp_text(
                to_waid,
                "Hubo un error procesando tu consulta. Intenta de nuevo o contacta a un asesor."
            )
        except Exception as e2:
            print("ERROR_SENDING_FAILSAFE:", repr(e2))

# ---------- ENVÍO MANUAL PARA PRUEBAS ----------
@app.get("/send-test")
async def send_test(to: str):
    """Envía la plantilla hello_world para probar salidas sin depender del webhook."""
    url = f"https://graph.facebook.com/{WA_API_VER}/{WA_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,  # ej. 57XXXXXXXXXX
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}"},
            json=payload,
        )
    try:
        return JSONResponse({"status": r.status_code, "json": r.json()})
    except Exception:
        return JSONResponse({"status": r.status_code, "text": r.text})
