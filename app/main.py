# app/main.py
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from .settings import get_settings
from .whatsapp import send_whatsapp_text
from .rag import answer_with_rag

app = FastAPI()
s = get_settings()

@app.get("/healthz")
async def healthz():
    return {"ok": True}

@app.get("/webhook")
async def verify(
    mode: str | None = Query(None, alias="hub.mode"),
    challenge: str | None = Query(None, alias="hub.challenge"),
    verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    if mode == "subscribe" and verify_token == s.wa_verify_token:
        # Meta espera el challenge como texto plano
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("forbidden", status_code=403)

@app.post("/webhook")
async def webhook(req: Request):
    body = await req.json()
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for m in value.get("messages", []):
                msg_type = m.get("type")
                from_id = m.get("from")
                if msg_type == "text":
                    text = (m.get("text") or {}).get("body", "").strip()
                elif msg_type == "button":
                    text = (m.get("button") or {}).get("text", "").strip()
                elif msg_type == "interactive":
                    text = (m.get("interactive") or {}).get("button_reply", {}).get("title", "").strip()
                else:
                    text = ""

                if from_id and text:
                    reply = await answer_with_rag(text)
                    await send_whatsapp_text(from_id, reply)

    return JSONResponse({"status": "ok"})
