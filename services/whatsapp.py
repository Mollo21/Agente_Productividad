import httpx
import config
import logging

logger = logging.getLogger(__name__)

async def send_whatsapp_message(to: str, message: str):
    """Envía un mensaje de texto vía WhatsApp Cloud API."""
    url = f"https://graph.facebook.com/v18.0/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message} # Limitar longitud si es muy largo
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"Error enviando mensaje WA: {response.text}")
        return response.json()

async def download_whatsapp_media(media_id: str) -> bytes:
    """Descarga un archivo multimedia (audio) desde WhatsApp."""
    url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        # 1. Obtener la URL del media
        res = await client.get(url, headers=headers)
        media_url = res.json().get("url")
        
        if media_url:
            # 2. Descargar el archivo real
            media_res = await client.get(media_url, headers=headers)
            return media_res.content
    return None
