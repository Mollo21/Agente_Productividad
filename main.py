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

@app.get("/diagnostico")
def diagnostico():
    """Endpoint para verificar que TODOS los servicios están funcionando."""
    import os
    from services import google_api
    
    results = {}
    
    # 1. Google Credentials
    creds_from_env = bool(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    creds_from_file = os.path.exists(config.GOOGLE_CREDENTIALS_FILE)
    results["google_credentials"] = {
        "from_env_var": creds_from_env,
        "from_file": creds_from_file,
        "method": "ENV_VAR" if creds_from_env else ("FILE" if creds_from_file else "NINGUNO ❌"),
    }
    
    # 2. Google Calendar
    if google_api.calendar_service:
        try:
            # Intentar leer eventos (solo 1, para probar)
            import datetime
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events = google_api.calendar_service.events().list(
                calendarId=google_api.CALENDAR_ID,
                timeMin=now, maxResults=1, singleEvents=True
            ).execute()
            results["google_calendar"] = "✅ CONECTADO - Acceso a " + google_api.CALENDAR_ID
        except Exception as e:
            results["google_calendar"] = f"❌ ERROR: {str(e)[:200]}"
    else:
        results["google_calendar"] = "❌ NO INICIALIZADO - calendar_service es None"
    
    # 3. Google Sheets
    if google_api.sheets_service and config.GOOGLE_SHEETS_ID:
        try:
            google_api.sheets_service.spreadsheets().get(
                spreadsheetId=config.GOOGLE_SHEETS_ID
            ).execute()
            results["google_sheets"] = "✅ CONECTADO"
        except Exception as e:
            results["google_sheets"] = f"❌ ERROR: {str(e)[:200]}"
    else:
        results["google_sheets"] = "❌ NO INICIALIZADO"
    
    # 4. Groq API Key
    results["groq_api_key"] = "✅ Configurada" if config.GROQ_API_KEY else "❌ NO configurada"
    
    # 5. WhatsApp
    results["whatsapp_token"] = "✅ Configurado" if config.WHATSAPP_TOKEN else "❌ NO configurado"
    results["whatsapp_phone_id"] = config.WHATSAPP_PHONE_NUMBER_ID or "❌ NO configurado"
    
    return {"diagnostico": results}

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
