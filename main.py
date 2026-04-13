from fastapi import FastAPI, BackgroundTasks, Request, Response
from pydantic import BaseModel
import config
from services import whatsapp, llm, scheduler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Personal Agent")

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando scheduler de suscripciones...")
    scheduler.start_scheduler()

@app.get("/")
def health_check():
    return {"status": "ok", "agent": "online"}

@app.get("/webhook")
def verify_webhook(request: Request):
    """Endpoint de verificación para Meta WhatsApp API."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == config.VERIFY_TOKEN:
            logger.info("Webhook verificado correctamente.")
            return Response(content=challenge, status_code=200)
    return Response(content="Prohibido", status_code=403)

async def process_incoming_message(value: dict):
    """Procesa el mensaje entrante en segundo plano."""
    try:
        messages = value.get("messages", [])
        if not messages:
            return

        msg = messages[0]
        phone_number = msg.get("from")
        msg_type = msg.get("type")
        
        user_text = ""
        
        if msg_type == "text":
            user_text = msg["text"]["body"]
        elif msg_type == "audio":
            # Descargar audio y transcribir
            media_id = msg["audio"]["id"]
            audio_bytes = await whatsapp.download_whatsapp_media(media_id)
            if audio_bytes:
                user_text = await llm.transcribe_audio(audio_bytes)
                await whatsapp.send_whatsapp_message(phone_number, f"🎤 _Escuché: '{user_text}'_\nAnalizando...")
        else:
            user_text = "[Mensaje no soportado, dile al usuario que solo aceptas texto o voz]"

        if not user_text:
            return

        # Enviar al Agente LLM
        response_text = await llm.agent_process(user_text, phone_number)
        
        # Enviar respuesta por WhatsApp
        await whatsapp.send_whatsapp_message(phone_number, response_text)

    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")

@app.post("/webhook")
async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
    """Recibe mensajes entrantes de WhatsApp."""
    data = await request.json()
    
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if "messages" in value:
                    # Derivar a tarea en segundo plano para responder HTTP 200 rápido a Meta
                    background_tasks.add_task(process_incoming_message, value)
    except Exception as e:
        logger.error(f"Error en webhook post: {e}")
        
    return {"status": "received"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
