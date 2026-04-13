from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.whatsapp import send_whatsapp_message
import config
from services.search import search_web
# Eliminamos el import global para evitar importación circular

scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

# Diccionario simple en memoria para guardar suscripciones (idealmente guardar en DB/Sheets)
subscriptions = {}

async def run_subscription(topic: str, phone_number: str):
    """Ejecuta la suscripción: busca la info y se la envía al usuario."""
    from services.llm import generate_response
    # 1. Buscar en la web sobre el topic
    search_results = search_web(f"Últimas noticias o información sobre: {topic}")
    
    # 2. Resumir con LLM
    prompt = f"Resume la siguiente información sobre '{topic}' para un mensaje rápido de WhatsApp:\n{search_results}"
    resumen = await generate_response(prompt)
    
    # 3. Enviar mensaje
    await send_whatsapp_message(phone_number, f"🔔 *Tu actualización de: {topic}*\n\n{resumen}")

def add_subscription(topic: str, cron_expression: str, phone_number: str):
    """
    Agrega una rutina. cron_expression puede ser '0 9 * * *' para todos los días a las 9am.
    """
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    
    # Valores por defecto: todos los días a las 9 AM
    hour = 9
    minute = 0
    # Simplificación: asumiremos 9AM diario por defecto si el LLM no envía cron completo
    
    job = scheduler.add_job(
        run_subscription,
        CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
        args=[topic, phone_number],
        id=job_id,
        replace_existing=True
    )
    subscriptions[job_id] = topic
    return f"Suscripción creada: Te enviaré info sobre '{topic}' todos los días a las {hour}:{minute:02d}."

def remove_subscription(topic: str, phone_number: str):
    """Elimina una rutina."""
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        if job_id in subscriptions:
            del subscriptions[job_id]
        return f"Suscripción de '{topic}' cancelada correctamente."
    return f"No tenías ninguna suscripción activa para '{topic}'."
    
def start_scheduler():
    scheduler.start()
