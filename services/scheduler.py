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

# Memoria temporal para la sesión actual
subscriptions_memory = {}

async def run_subscription(topic: str, phone_number: str):
    """Ejecuta la suscripción: busca la info de forma comprensiva y se la envía al usuario."""
    from services.llm import generate_response
    
    # 1. Búsqueda comprensiva (múltiples ángulos, no literal)
    search_results = search_topic_comprehensive(topic)
    
    # 2. Resumir con LLM para un mensaje WhatsApp conciso y útil
    prompt = f"""Eres un analista de noticias experto. Con la siguiente información sobre '{topic}', crea un resumen ejecutivo.
    IMPORTANTE: Si el tema es sobre el IPSA o valores financieros, menciona el valor actual si aparece en la información.
    
    REGLAS:
    - Máximo 5 puntos clave
    - Usa emojis relevantes
    - Sé directo y útil
    
    INFORMACIÓN RECOPILADA:
    {search_results}"""

    resumen = await generate_response(prompt)
    
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    fecha_str = ahora.strftime("%d/%m/%Y %H:%M")
    
    msg = f"🔔 *Actualización diaria: {topic}*\n📅 {fecha_str}\n\n{resumen}"
    await send_whatsapp_message(phone_number, msg)

def add_subscription(topic: str, cron_expression: str, phone_number: str):
    """Agrega rutina diaria con persistencia en Google Sheets."""
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    
    hour = 9
    minute = 0
    try:
        if ":" in cron_expression:
            hour, minute = map(int, cron_expression.split(":"))
        else:
            parts = cron_expression.strip().split()
            if len(parts) >= 2:
                minute = int(parts[0])
                hour = int(parts[1])
    except: pass
    
    # Cargar en el scheduler
    scheduler.add_job(
        run_subscription,
        CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
        args=[topic, phone_number],
        id=job_id,
        replace_existing=True
    )
    
    # Guardar en memoria de sesión
    subscriptions_memory[job_id] = {"topic": topic, "phone": phone_number, "hour": hour, "minute": minute}
    
    # GUARDAR EN GOOGLE SHEETS PARA SIEMPRE
    from services.google_api import save_subscription
    save_subscription(topic, hour, minute, phone_number)
    
    return f"✅ Suscripción creada: Te enviaré un resumen completo sobre '{topic}' todos los días a las {hour:02d}:{minute:02d}. Guardado en Google Sheets."

def remove_subscription(topic: str, phone_number: str):
    job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone_number}"
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    if job_id in subscriptions_memory:
        del subscriptions_memory[job_id]
        
    from services.google_api import delete_subscription_sheet
    delete_subscription_sheet(topic, phone_number)
    
    return f"✅ Suscripción de '{topic}' eliminada."

def list_subscriptions(phone_number: str) -> str:
    # Combinar memoria de sesión con lo que hay en el sheet (simplificado: leer del sheet)
    from services.google_api import get_all_subscriptions
    subs = get_all_subscriptions()
    user_subs = [s for s in subs if s[0] == phone_number]
    
    if not user_subs:
        return "No tienes suscripciones activas registradas."
    
    lines = [f"• {s[1]} — todos los días a las {s[2]}" for s in user_subs]
    return "📋 *Tus suscripciones activas:*\n" + "\n".join(lines)

async def send_reminder(phone_number: str, text: str, event_time_iso: str = None, run_at_iso: str = None):
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    
    if event_time_iso:
        try:
            event_dt = dateutil.parser.isoparse(event_time_iso)
            if event_dt.tzinfo is None: event_dt = tz.localize(event_dt)
            mins_left = int((event_dt.timestamp() - ahora.timestamp()) / 60)
            if mins_left < 0: mins_left = 0
            msg = f"⏰ Recordatorio: {text}\n📅 {event_dt.strftime('%d-%m-%Y %H:%M')}\n🚨 ¡Comienza en {mins_left} minutos!"
        except:
            msg = f"🔔 Recordatorio: {text}"
    else:
        msg = f"🔔 Recordatorio: {text}"
        
    await send_whatsapp_message(phone_number, msg)
    
    # Eliminar de Google Sheets de forma asíncrona para no bloquear
    if run_at_iso:
        from services.google_api import delete_reminder_sheet
        import asyncio
        asyncio.create_task(asyncio.to_thread(delete_reminder_sheet, phone_number, text, run_at_iso))

def add_reminder_at_datetime(iso_datetime: str, texto: str, phone_number: str, event_time_iso: str = None) -> str:
    try:
        tz = pytz.timezone(config.TIMEZONE)
        run_at = dateutil.parser.isoparse(iso_datetime)
        if run_at.tzinfo is None: run_at = tz.localize(run_at)
        
        if run_at <= datetime.datetime.now(tz):
            return "La hora ya pasó."
            
        scheduler.add_job(
            send_reminder, 'date', run_date=run_at,
            args=[phone_number, texto, event_time_iso or iso_datetime, iso_datetime]
        )
        
        from services.google_api import save_reminder_sheet
        save_reminder_sheet(phone_number, texto, iso_datetime, event_time_iso or iso_datetime)
        
        return f"✅ Recordatorio programado para las {run_at.strftime('%H:%M')}."
    except Exception as e:
        return f"Error: {e}"

def start_scheduler():
    """Inicia y carga suscripciones y recordatorios desde Sheets."""
    scheduler.start()
    from services.google_api import get_all_subscriptions, get_all_reminders_sheet
    subs = get_all_subscriptions()
    count = 0
    for s in subs:
        if len(s) >= 3:
            try:
                phone, topic, time_str = s[0], s[1], s[2]
                hour, minute = map(int, time_str.split(":"))
                job_id = f"sub_{topic.replace(' ', '_').lower()}_{phone}"
                scheduler.add_job(
                    run_subscription, CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
                    args=[topic, phone], id=job_id, replace_existing=True
                )
                count += 1
            except: continue
    logger.info(f"Scheduler listo. {count} suscripciones cargadas.")
    
    rems = get_all_reminders_sheet()
    count_rems = 0
    tz = pytz.timezone(config.TIMEZONE)
    for r in rems:
        if len(r) >= 4:
            try:
                phone, text, run_at_iso, event_iso = r[0], r[1], r[2], r[3]
                run_at = dateutil.parser.isoparse(run_at_iso)
                if run_at.tzinfo is None: run_at = tz.localize(run_at)
                
                if run_at <= datetime.datetime.now(tz):
                    # Si ya pasó, ejecutar en 5 segundos
                    run_at = datetime.datetime.now(tz) + datetime.timedelta(seconds=5)
                    
                scheduler.add_job(
                    send_reminder, 'date', run_date=run_at,
                    args=[phone, text, event_iso, run_at_iso]
                )
                count_rems += 1
            except Exception as e:
                logger.error(f"Error cargando recordatorio de Sheets: {e}")
                continue
    logger.info(f"Cargados {count_rems} recordatorios desde Sheets.")
