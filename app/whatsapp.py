# app/whatsapp.py
from .settings import get_settings
from .providers import http_post_json

GRAPH_URL_TMPL = "https://graph.facebook.com/{ver}/{phone_id}/messages"

async def send_whatsapp_text(to_number: str, body: str) -> dict:
    s = get_settings()
    url = GRAPH_URL_TMPL.format(ver=s.wa_api_version, phone_id=s.wa_phone_number_id)
    headers = {
        "Authorization": f"Bearer {s.wa_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    resp = await http_post_json(url, headers, payload)
    try:
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "text": (resp.text[:300] if resp is not None else "")}
