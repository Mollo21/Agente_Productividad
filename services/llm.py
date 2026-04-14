import httpx
import config
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from services import google_api, search, scheduler
import json
import datetime
import pytz
import dateutil.parser
import logging

logger = logging.getLogger(__name__)

# Setup del LLM
llm = ChatGroq(
    temperature=0, 
    model_name="meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=config.GROQ_API_KEY
)

# Mapa de emojis por categoría de evento
EMOJI_MAP = {
    "reunión": "👥", "reunion": "👥", "meeting": "👥", "equipo": "👥",
    "doctor": "🏥", "médico": "🏥", "medico": "🏥", "dentista": "🦷", "salud": "🏥",
    "comida": "🍽️", "almuerzo": "🍽️", "cena": "🍽️", "sushi": "🍣", "pizza": "🍕",
    "comprar": "🛒", "supermercado": "🛒", "compras": "🛒",
    "estudio": "📚", "estudiar": "📚", "tarea": "📚", "prueba": "📝", "examen": "📝", "clase": "📚",
    "trabajo": "💼", "oficina": "💼", "proyecto": "💼",
    "ejercicio": "🏋️", "gym": "🏋️", "deporte": "⚽", "correr": "🏃",
    "cumpleaños": "🎂", "fiesta": "🎉", "celebración": "🎉",
    "viaje": "✈️", "vuelo": "✈️", "pasaje": "✈️",
    "llamada": "📞", "llamar": "📞",
    "pago": "💰", "pagar": "💰", "banco": "🏦",
    "juicio": "⚖️", "abogado": "⚖️", "derecho": "⚖️",
}


def get_emoji_for_event(titulo: str) -> str:
    """Selecciona el emoji más relevante para el título del evento."""
    titulo_lower = titulo.lower()
    for keyword, emoji in EMOJI_MAP.items():
        if keyword in titulo_lower:
            return emoji
    return "📌"


def build_event_response(titulo: str, fecha_dt: datetime.datetime, fin_dt: datetime.datetime = None, 
                         recordatorio_dt: datetime.datetime = None, all_day: bool = False,
                         calendar_ok: bool = True) -> str:
    """Construye la respuesta formateada para eventos/recordatorios."""
    
    emoji = get_emoji_for_event(titulo)
    fecha_str = fecha_dt.strftime('%d-%m-%Y')
    
    msg = f"¡Listo! He agregado el siguiente evento a tu calendario:\n\n"
    msg += f"📅 Fecha: {fecha_str}\n\n"
    
    if all_day:
        msg += f"{emoji} {titulo} - Todo el día\n"
        msg += f"  📝 {titulo}\n"
        if recordatorio_dt:
            msg += f"  🔔 Te recordaré el mismo día a las {recordatorio_dt.strftime('%H:%M')}\n"
        else:
            msg += f"  🔔 Te recordaré a las 09:00\n"
    else:
        hora_inicio = fecha_dt.strftime('%H:%M')
        hora_fin = fin_dt.strftime('%H:%M') if fin_dt else (fecha_dt + datetime.timedelta(hours=1)).strftime('%H:%M')
        msg += f"{emoji} {titulo} - {hora_inicio} a {hora_fin}\n"
        msg += f"  📝 {titulo}\n"
        
        if recordatorio_dt:
            diff = fecha_dt - recordatorio_dt
            mins_before = int(diff.total_seconds() / 60)
            if mins_before <= 0:
                msg += f"  🔔 Te recordaré cuando empiece (a las {hora_inicio})\n"
            else:
                msg += f"  🔔 Te recordaré {mins_before} minutos antes (a las {recordatorio_dt.strftime('%H:%M')})\n"
        else:
            msg += f"  🔔 Te recordaré cuando empiece (a las {hora_inicio})\n"
    
    if not calendar_ok:
        msg += "\n⚠️ Nota: Hubo un problema guardando en Google Calendar, pero el recordatorio por WhatsApp sí quedó programado.\n"
    
    # Frase amigable contextual
    titulo_lower = titulo.lower()
    if any(w in titulo_lower for w in ["tarea", "estudi", "prueba", "examen"]):
        msg += "\n¡Mucho éxito con los estudios! 💪 ¿Hay algo más en lo que pueda ayudarte hoy?"
    elif any(w in titulo_lower for w in ["reunión", "reunion", "equipo", "meeting"]):
        msg += "\n¡Éxito en la reunión! ¿Hay algo más en lo que pueda ayudarte hoy?"
    elif any(w in titulo_lower for w in ["doctor", "médico", "dentista", "salud"]):
        msg += "\n¡Espero que todo salga bien! ¿Hay algo más en lo que pueda ayudarte hoy?"
    elif any(w in titulo_lower for w in ["cumpleaño", "fiesta", "celebr"]):
        msg += "\n¡Que sea una gran celebración! 🎉 ¿Hay algo más en lo que pueda ayudarte hoy?"
    elif any(w in titulo_lower for w in ["compr", "sushi", "comida", "almuerzo", "cena"]):
        msg += "\n¡Buen provecho! 😋 ¿Hay algo más en lo que pueda ayudarte hoy?"
    else:
        msg += "\n¿Hay algo más en lo que pueda ayudarte hoy?"
    
    return msg

def safe_float(v):
    try: return float(str(v).replace('"', '').replace('$', '').replace(',', '').replace('.', '').strip())
    except: return 0.0

# ==================== HERRAMIENTAS ====================

@tool
def registrar_gasto(monto: str, categoria: str, descripcion: str) -> str:
    """Registra un gasto económico del usuario en la planilla de finanzas."""
    return google_api.log_expense(safe_float(monto), categoria, descripcion)

@tool
def consultar_gastos(mes_busqueda: str = "") -> str:
    """Consulta los gastos del usuario y genera un reporte resumido agrupado por categorías.
    Usa esta herramienta cuando el usuario pida un resumen, balance, reporte mensual o quiera saber cuánto ha gastado.
    Opcionalmente acepta el nombre de un mes (ej: 'marzo') para filtrar.
    """
    return google_api.get_expenses(mes_busqueda)

@tool
def agendar(titulo: str, inicio_iso: str, fin_iso: str = "", recordatorio_iso: str = "", todo_el_dia: bool = False) -> str:
    """Agenda un evento en el calendario Y programa un recordatorio por WhatsApp.
    USA ESTA HERRAMIENTA SIEMPRE que el usuario pida agendar, recordar, o programar CUALQUIER COSA con fecha.
    """
    return "EVENT_SCHEDULED_CHECK_BACKGROUND"

@tool
def consultar_calendario(fecha_inicio: str = "", fecha_fin: str = "") -> str:
    """Consulta los eventos del calendario del usuario.
    """
    return "CALENDAR_QUERY_PENDING"

@tool
def guardar_memoria(categoria: str, detalle: str) -> str:
    """Guarda un dato personal para recordar a futuro.
    """
    return google_api.save_memory(categoria, detalle)

@tool
def consultar_memoria(consulta: str) -> str:
    """Busca en la memoria datos guardados previamente.
    """
    return google_api.search_memory(consulta)

@tool
def buscar_internet(query: str) -> str:
    """Busca información general y actualizada en internet.
    """
    return search.search_web(query)

@tool
def buscar_noticias(query: str) -> str:
    """Busca NOTICIAS recientes sobre un tema.
    """
    return search.search_news(query)

@tool  
def crear_suscripcion(tema: str, hora_exacta: str = "09:00") -> str:
    """Crea una alerta diaria. Recibirás un resumen sobre el tema a la hora indicada.
    
    Args:
        tema: Tema a seguir (ej: 'IPSA Chile', 'Bitcoin', 'Noticias Cobre')
        hora_exacta: Hora en formato HH:MM (ej: '09:35', '21:00'). Defecto '09:00'
    """
    return "SUBSCRIPTION_CREATE_PENDING"

@tool
def listar_suscripciones() -> str:
    """Muestra todas las suscripciones/alertas diarias activas del usuario."""
    return "SUBSCRIPTION_LIST_PENDING"

@tool
def cancelar_suscripcion(tema: str) -> str:
    """Cancela una alerta diaria.
    """
    return "SUBSCRIPTION_CANCEL_PENDING"


# Bind tools
tools = [
    registrar_gasto, consultar_gastos,
    agendar, consultar_calendario,
    guardar_memoria, consultar_memoria,
    buscar_internet, buscar_noticias,
    crear_suscripcion, listar_suscripciones, cancelar_suscripcion,
]
llm_with_tools = llm.bind_tools(tools)


# ==================== SYSTEM PROMPT ====================

system_prompt = """Eres el Asistente Personal de Diego. Eres su segundo cerebro digital vía WhatsApp.
Sé conciso, amigable, directo y usa emojis donde aporten valor.

═══════════════════════════════════════════════
🔴 REGLAS ABSOLUTAS 🔴
═══════════════════════════════════════════════

1. CUANDO EL USUARIO PIDA ALGO, HAZLO DE INMEDIATO. No preguntes confirmación.
2. CUALQUIER pedido que mencione una fecha, día, hora o que use palabras como "recuérdame", "agenda", "pon", "anota" → USA la herramienta "agendar" SIEMPRE.
3. Ejemplos:
   - "recuérdame mañana a las 9" → agendar (con hora)
   - "mañana 9pm hacer tarea" → agendar (con hora)
   - "recuérdame el día 15 cumpleaños de Tomy" → agendar (todo_el_dia=true)
   - "el 20 es la prueba de derecho" → agendar (todo_el_dia=true)
4. NUNCA respondas "no puedo recordar" o "¿quieres que lo agende?". Si tiene fecha/día, USA agendar DIRECTAMENTE.
5. Si solo dice un día sin hora → pon todo_el_dia=true. Si dice hora → pon todo_el_dia=false.

═══════════════════════════════════════════════
📅 REGLAS DE FECHAS
═══════════════════════════════════════════════

CÁLCULO DE FECHAS - CRÍTICO:
- "mañana" = fecha de hoy + 1 día
- "pasado mañana" = fecha de hoy + 2 días
- "el lunes" = el próximo lunes
- "en una hora" = hora actual + 1 hora
- "en 30 minutos" = hora actual + 30 minutos

FORMATO: YYYY-MM-DDTHH:MM:SS-04:00

IMPORTANTE: Cuando la herramienta agendar retorne un resultado, DEVUELVE ESE RESULTADO TAL CUAL al usuario, SIN modificarlo. El mensaje ya viene formateado perfectamente.

═══════════════════════════════════════════════
🔍 REGLAS DE BÚSQUEDA Y FINANZAS
═══════════════════════════════════════════════

1. NUNCA busques el texto LITERAL del usuario. SIEMPRE optimiza el query.
2. Si piden PRECIOS o VALORES (IPSA, dólar, cobre):
   - BUSCA: "[Tema] precio hoy tiempo real" o "[Tema] valor actualizado hoy"
   - Si piden Yahoo Finance, busca: "[Tema] Yahoo Finance today"
3. Para NOTICIAS → usa buscar_noticias
4. Para INFO GENERAL → usa buscar_internet

Cuando presentes resultados:
- Prioriza información que tenga la fecha de HOY.
- Si ves que un dato es de hace meses, advierte que es antiguo.
- Resume lo valioso y usa emojis.

═══════════════════════════════════════════════
💰 CLIMA Y PESOS
═══════════════════════════════════════════════
- Moneda: CLP (pesos chilenos). 15 lucas = 15000.
- Ubicación por defecto: Chile.
"""

# ==================== HISTORIAL ====================

chat_history = {}


# ==================== PROCESAMIENTO PRINCIPAL ====================

async def agent_process(text: str, phone_number: str) -> str:
    """Procesa un mensaje del usuario y retorna la respuesta del agente."""
    
    if phone_number not in chat_history:
        chat_history[phone_number] = []
    
    history = chat_history[phone_number][-10:]
    
    # Contexto temporal
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    
    dias_semana = {
        'Monday': 'lunes', 'Tuesday': 'martes', 'Wednesday': 'miércoles',
        'Thursday': 'jueves', 'Friday': 'viernes', 'Saturday': 'sábado', 'Sunday': 'domingo'
    }
    meses = {
        'January': 'enero', 'February': 'febrero', 'March': 'marzo',
        'April': 'abril', 'May': 'mayo', 'June': 'junio',
        'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
        'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
    }
    
    dia_semana = dias_semana.get(ahora.strftime('%A'), ahora.strftime('%A'))
    mes = meses.get(ahora.strftime('%B'), ahora.strftime('%B'))
    
    manana = ahora + datetime.timedelta(days=1)
    
    fecha_context = (
        f"Fecha actual: {dia_semana}, {ahora.day} de {mes} de {ahora.year}\n"
        f"Hora actual: {ahora.strftime('%H:%M:%S')}\n"
        f"Timezone: America/Santiago (UTC-04:00)\n"
        f"Mañana es: {manana.strftime('%Y-%m-%d')} ({dias_semana.get(manana.strftime('%A'), manana.strftime('%A'))})\n"
        f"ISO actual: {ahora.isoformat()}"
    )

    system_content = system_prompt + f"\n\n{fecha_context}\nTeléfono del usuario: {phone_number}"
    
    system_msg = SystemMessage(content=system_content)
    user_msg = HumanMessage(content=text)
    
    messages = [system_msg] + history + [user_msg]
    
    try:
        response = llm_with_tools.invoke(messages)
        
        chat_history[phone_number].append(user_msg)
        
        max_iterations = 5
        iteration = 0
        
        while response.tool_calls and iteration < max_iterations:
            iteration += 1
            
            chat_history[phone_number].append(response)
            messages.append(response)
            
            tool_results_summary = []
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                logger.info(f"Ejecutando herramienta: {tool_name} con args: {tool_args}")
                
                result_str = execute_tool(tool_name, tool_args, phone_number)
                
                logger.info(f"Resultado de {tool_name}: {result_str[:200]}...")
                
                tool_results_summary.append(result_str)
                
                tool_msg = ToolMessage(
                    content=result_str,
                    tool_call_id=tool_call["id"]
                )
                messages.append(tool_msg)
                chat_history[phone_number].append(tool_msg)
            
            # Para herramientas que generan respuesta formateada (agendar),
            # devolver el resultado directamente sin re-invocar al LLM
            if any(tc["name"] == "agendar" for tc in response.tool_calls):
                formatted_response = "\n".join(tool_results_summary)
                response = AIMessage(content=formatted_response)
                break
            
            try:
                response = llm_with_tools.invoke(messages)
            except Exception as e:
                logger.warning(f"Error en segunda invocación del LLM (recuperando): {e}")
                combined = "\n".join(tool_results_summary)
                response = AIMessage(content=combined)
        
        chat_history[phone_number].append(response)
        chat_history[phone_number] = chat_history[phone_number][-20:]
        
        return response.content
    except Exception as e:
        logger.error(f"Error en agent_process: {e}", exc_info=True)
        return f"⚠️ Ups, ocurrió un error procesando tu mensaje. Intenta de nuevo. ({str(e)[:100]})"


# ==================== EJECUCIÓN DE HERRAMIENTAS ====================

def execute_tool(name: str, args: dict, phone_number: str) -> str:
    """Ejecuta una herramienta y retorna el resultado como string."""
    
    def execute_agendar(a):
        """Crea evento en calendario + recordatorio + devuelve respuesta formateada."""
        tz = pytz.timezone(config.TIMEZONE)
        is_all_day = a.get('todo_el_dia', False)
        
        # Parsear fecha de inicio
        try:
            inicio_dt = dateutil.parser.isoparse(a['inicio_iso'])
            if inicio_dt.tzinfo is None:
                inicio_dt = tz.localize(inicio_dt)
        except Exception as e:
            return f"❌ Error con la fecha de inicio: {e}"
        
        # Parsear fecha de fin (opcional)
        fin_iso = a.get('fin_iso', '').strip()
        if fin_iso:
            try:
                fin_dt = dateutil.parser.isoparse(fin_iso)
                if fin_dt.tzinfo is None:
                    fin_dt = tz.localize(fin_dt)
            except:
                fin_dt = inicio_dt + datetime.timedelta(hours=1)
        else:
            fin_dt = inicio_dt + datetime.timedelta(hours=1)
        
        # Recordatorio: si no se especifica, usar misma hora que inicio
        recordatorio_iso = a.get('recordatorio_iso', '').strip()
        if recordatorio_iso:
            try:
                recordatorio_dt = dateutil.parser.isoparse(recordatorio_iso)
                if recordatorio_dt.tzinfo is None:
                    recordatorio_dt = tz.localize(recordatorio_dt)
            except:
                recordatorio_dt = inicio_dt
        else:
            recordatorio_dt = inicio_dt
        
        # 1. Crear evento en Google Calendar
        cal_result = google_api.add_calendar_event(
            a['titulo'], a['inicio_iso'], fin_dt.isoformat(), 
            all_day=is_all_day
        )
        logger.info(f"Calendar result: {cal_result}")
        calendar_ok = "CALENDAR_OK" in cal_result
        
        # 2. Programar recordatorio por WhatsApp
        reminder_result = scheduler.add_reminder_at_datetime(
            recordatorio_dt.isoformat(),
            a['titulo'],
            phone_number,
            event_time_iso=a['inicio_iso']
        )
        logger.info(f"Reminder result: {reminder_result}")
        
        # 3. Construir respuesta formateada (GARANTIZADA por código Python)
        return build_event_response(
            a['titulo'], inicio_dt, fin_dt, recordatorio_dt, 
            all_day=is_all_day, calendar_ok=calendar_ok
        )

    def execute_query_calendar(a):
        """Consulta eventos del calendario."""
        tz = pytz.timezone(config.TIMEZONE)
        ahora = datetime.datetime.now(tz)
        
        fecha_inicio = a.get('fecha_inicio', '')
        fecha_fin = a.get('fecha_fin', '')
        
        if not fecha_inicio:
            fecha_inicio = ahora.replace(hour=0, minute=0, second=0).isoformat()
        if not fecha_fin:
            fecha_fin = (ahora + datetime.timedelta(days=7)).replace(hour=23, minute=59, second=59).isoformat()
        
        return google_api.get_calendar_events(fecha_inicio, fecha_fin)

    tool_map = {
        "registrar_gasto": lambda a: google_api.log_expense(
            safe_float(a['monto']), a['categoria'], a['descripcion']
        ),
        "consultar_gastos": lambda a: google_api.get_expenses(a.get('mes_busqueda', '')),
        "agendar": lambda a: execute_agendar(a),
        "consultar_calendario": lambda a: execute_query_calendar(a),
        "guardar_memoria": lambda a: google_api.save_memory(a['categoria'], a['detalle']),
        "consultar_memoria": lambda a: google_api.search_memory(a['consulta']),
        "buscar_internet": lambda a: search.search_web(a['query']),
        "buscar_noticias": lambda a: search.search_news(a['query']),
        "crear_suscripcion": lambda a: scheduler.add_subscription(a['tema'], a.get('hora_exacta', '09:00'), phone_number),
        "listar_suscripciones": lambda a: scheduler.list_subscriptions(phone_number),
        "cancelar_suscripcion": lambda a: scheduler.remove_subscription(a['tema'], phone_number),
    }
    
    if name in tool_map:
        try:
            return tool_map[name](args)
        except Exception as e:
            logger.error(f"Error ejecutando herramienta {name}: {e}", exc_info=True)
            return f"❌ Error ejecutando {name}: {str(e)}"
    
    return f"⚠️ Herramienta '{name}' no encontrada."


# ==================== UTILIDADES ====================

async def transcribe_audio(audio_bytes: bytes) -> str:
    """Usa la API de Groq para transcribir audio usando Whisper."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}"
    }
    files = {
        'file': ('audio.ogg', audio_bytes, 'audio/ogg')
    }
    data = {
        'model': 'whisper-large-v3',
        'language': 'es'
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, headers=headers, files=files, data=data)
        if res.status_code == 200:
            return res.json().get("text", "")
        else:
            raise Exception(f"Error Whisper: {res.text}")


async def generate_response(prompt: str) -> str:
    """Uso general para resúmenes sin herramientas."""
    res = llm.invoke(prompt)
    return res.content
