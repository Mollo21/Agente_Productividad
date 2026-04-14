from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from services.whatsapp import send_whatsapp_message
import config
from services.search import search_topic_comprehensive
import logging
import datetime
import pytz
import dateutil.parser

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)

# Diccionario simple en memoria para guardar suscripciones (idealmente guardar en DB/Sheets)
subscriptions = {}


async def run_subscription(topic: str, phone_number: str):
    """Ejecuta la suscripción: busca la info de forma comprensiva y se la envía al usuario."""
    from services.llm import generate_response
    
    # 1. Búsqueda comprensiva (múltiples ángulos, no literal)
    search_results = search_topic_comprehensive(topic)
    
    # 2. Resumir con LLM para un mensaje WhatsApp conciso y útil
    prompt = f"""Eres un analista de noticias. Con la siguiente información sobre '{topic}', crea un resumen ejecutivo para WhatsApp.

REGLAS:
- Máximo 5 puntos clave, cada uno en 1-2 líneas
- Usa emojis relevantes
- Si hay datos numéricos (precios, %, etc.) inclúyelos
- Incluye la tendencia general (sube, baja, estable, etc.) si aplica
- Sé directo y útil, no rellenes

INFORMACIÓN RECOPILADA:
{search_results}"""

    resumen = await generate_response(prompt)
    
    # 3. Enviar mensaje
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    fecha_str = ahora.strftime("%d/%m/%Y %H:%M")
    
    msg = f"🔔 *Actualización diaria: {topic}*\n📅 {fecha_str}\n\n{resumen}"
    await send_whatsapp_message(phone_number, msg)


def add_subscription(topic: str, cron_expression: str, phone_number: str):
    """
    Agrega una rutina diaria.
    """
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    
    # Parsear cron expression si viene completa, sino usar defaults de 9AM
    hour = 9
    minute = 0
    try:
        parts = cron_expression.strip().split()
        if len(parts) >= 2:
            minute = int(parts[0])
            hour = int(parts[1])
    except (ValueError, IndexError):
        pass
    
    job = scheduler.add_job(
        run_subscription,
        CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
        args=[topic, phone_number],
        id=job_id,
        replace_existing=True
    )
    subscriptions[job_id] = {"topic": topic, "phone": phone_number, "hour": hour, "minute": minute}
    return f"✅ Suscripción creada: Te enviaré un resumen completo sobre '{topic}' todos los días a las {hour}:{minute:02d}."


def remove_subscription(topic: str, phone_number: str):
    """Elimina una rutina."""
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        if job_id in subscriptions:
            del subscriptions[job_id]
        return f"✅ Suscripción de '{topic}' cancelada correctamente."
    return f"No tenías ninguna suscripción activa para '{topic}'."


def list_subscriptions(phone_number: str) -> str:
    """Lista todas las suscripciones activas del usuario."""
    user_subs = {k: v for k, v in subscriptions.items() if phone_number in k}
    if not user_subs:
        return "No tienes suscripciones activas."
    
    lines = []
    for job_id, info in user_subs.items():
        if isinstance(info, dict):
            lines.append(f"• {info['topic']} — todos los días a las {info['hour']}:{info['minute']:02d}")
        else:
            lines.append(f"• {info}")
    
    return "📋 *Tus suscripciones activas:*\n" + "\n".join(lines)


async def send_reminder(phone_number: str, text: str, event_time_iso: str = None):
    """Tarea que envía el recordatorio por WhatsApp."""
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    
    msg = f"🔔 *RECORDATORIO*\n\n"
    msg += f"📝 {text}\n"
    
    if event_time_iso:
        try:
            event_dt = dateutil.parser.isoparse(event_time_iso)
            if event_dt.tzinfo is None:
                event_dt = tz.localize(event_dt)
            diff = event_dt - ahora
            mins_left = int(diff.total_seconds() / 60)
            if mins_left > 0:
                msg += f"⏰ El evento es en {mins_left} minutos ({event_dt.strftime('%H:%M')})\n"
            else:
                msg += f"⏰ ¡El evento empieza AHORA! ({event_dt.strftime('%H:%M')})\n"
            msg += f"📅 {event_dt.strftime('%d/%m/%Y')}"
        except Exception:
            msg += f"📅 {ahora.strftime('%d/%m/%Y %H:%M')}"
    else:
        msg += f"📅 {ahora.strftime('%d/%m/%Y %H:%M')}"
    
    await send_whatsapp_message(phone_number, msg)


def add_reminder_at_datetime(iso_datetime: str, texto: str, phone_number: str, event_time_iso: str = None) -> str:
    """
    Programa un recordatorio para una fecha/hora ISO específica.
    Esta es la función PRINCIPAL para recordatorios.
    iso_datetime: cuándo disparar el recordatorio
    event_time_iso: cuándo es el evento real (para mostrar en el mensaje)
    """
    try:
        tz = pytz.timezone(config.TIMEZONE)
        run_at = dateutil.parser.isoparse(iso_datetime)
        
        # Si no tiene timezone, asumir Chile
        if run_at.tzinfo is None:
            run_at = tz.localize(run_at)
        
        ahora = datetime.datetime.now(tz)
        if run_at <= ahora:
            return f"⚠️ La fecha/hora ({run_at.strftime('%d/%m/%Y %H:%M')}) ya pasó. No puedo programar un recordatorio en el pasado."
        
        scheduler.add_job(
            send_reminder,
            'date',
            run_date=run_at,
            args=[phone_number, texto, event_time_iso or iso_datetime]
        )
        return f"✅ Recordatorio programado: '{texto}' para el {run_at.strftime('%d/%m/%Y a las %H:%M')}."
    except Exception as e:
        logger.error(f"Error programando recordatorio: {e}")
        return f"❌ Error programando recordatorio: {str(e)}"


def add_reminder_minutes(minutos: int, texto: str, phone_number: str) -> str:
    """Programa un recordatorio para dentro de X minutos (mantener por compatibilidad)."""
    tz = pytz.timezone(config.TIMEZONE)
    run_at = datetime.datetime.now(tz) + datetime.timedelta(minutes=max(1, minutos))
    
    scheduler.add_job(
        send_reminder,
        'date',
        run_date=run_at,
        args=[phone_number, texto, None]
    )
    return f"✅ Te recordaré '{texto}' en {minutos} minutos (a las {run_at.strftime('%H:%M')}). "


def start_scheduler():
    scheduler.start()
    logger.info("Scheduler iniciado correctamente.")
