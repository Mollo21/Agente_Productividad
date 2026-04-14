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

# ==================== HERRAMIENTAS ====================

@tool
def registrar_gasto(monto: str, categoria: str, descripcion: str) -> str:
    """Registra un gasto económico del usuario.
    
    Args:
        monto: Monto en pesos chilenos (número, ej: '15000')
        categoria: Categoría del gasto (ej: 'Supermercado', 'Transporte', 'Comida')
        descripcion: Breve descripción del gasto
    """
    return "PENDING"

@tool
def consultar_gastos(mes_busqueda: str = "") -> str:
    """Consulta los gastos registrados del usuario. Puede filtrar por mes.
    
    Args:
        mes_busqueda: Opcional. Mes a buscar (ej: 'abril', '2024-04'). Vacío = últimos 20.
    """
    return google_api.get_expenses(mes_busqueda)

@tool
def programar_evento(titulo: str, inicio_iso: str, fin_iso: str, recordatorio_iso: str = "") -> str:
    """Crea un evento en Google Calendar Y programa un recordatorio automático.
    
    IMPORTANTE - Reglas para las fechas:
    - TODAS las fechas DEBEN estar en formato ISO 8601 con timezone Chile: YYYY-MM-DDTHH:MM:SS-04:00
    - Si el usuario dice "mañana a las 9", calcula la fecha exacta de mañana y pon las 09:00:00-04:00
    - Si no se especifica hora de fin, pon 1 hora después del inicio
    - recordatorio_iso es CUÁNDO enviar la notificación (NO cuántos minutos antes)
    
    Args:
        titulo: Nombre del evento
        inicio_iso: Fecha/hora de inicio en ISO 8601 (ej: '2026-04-15T09:00:00-04:00')
        fin_iso: Fecha/hora de fin en ISO 8601 (ej: '2026-04-15T10:00:00-04:00')
        recordatorio_iso: Fecha/hora de cuándo enviar el recordatorio en ISO 8601. Si el usuario dice 'avísame 15 min antes', calcula la hora del evento menos 15 minutos y escríbela aquí. Si dice 'recuérdame a las 8:50', pon esa hora. Si no pide recordatorio, déjalo vacío.
    """
    return "PENDING"

@tool
def consultar_calendario(fecha_inicio: str = "", fecha_fin: str = "") -> str:
    """Consulta los eventos del calendario del usuario.
    
    Args:
        fecha_inicio: Fecha desde cuándo buscar en ISO 8601 (ej: '2026-04-14T00:00:00-04:00'). Si vacío, busca desde hoy.
        fecha_fin: Fecha hasta cuándo buscar en ISO 8601 (ej: '2026-04-20T23:59:59-04:00'). Si vacío, busca los próximos 7 días.
    """
    return "PENDING"

@tool
def guardar_memoria(categoria: str, detalle: str) -> str:
    """Guarda un dato personal para recordar a futuro.
    
    Args:
        categoria: Tema o persona (ej: 'Llaves', 'Mamá', 'WiFi casa')
        detalle: Información a recordar (ej: 'Las dejé en el cajón azul', 'Cumple el 15 de marzo')
    """
    return google_api.save_memory(categoria, detalle)

@tool
def consultar_memoria(consulta: str) -> str:
    """Busca en la memoria datos guardados previamente.
    
    Args:
        consulta: Qué buscar (ej: 'llaves', 'cumpleaños mamá')
    """
    return google_api.search_memory(consulta)

@tool
def buscar_internet(query: str) -> str:
    """Busca información general y actualizada en internet. Úsala para cualquier consulta.
    IMPORTANTE: NO busques el texto literal del usuario. Genera un query de búsqueda OPTIMIZADO.
    
    Ejemplo:
    - Usuario dice: "cómo va el dólar" → query: "precio dólar Chile hoy cotización"  
    - Usuario dice: "qué pasó con Argentina" → query: "Argentina noticias hoy últimas"
    - Usuario dice: "cuánto cuesta el cobre" → query: "precio cobre internacional bolsa hoy"
    
    Args:
        query: Query de búsqueda optimizado (NO el texto literal del usuario)
    """
    return search.search_web(query)

@tool
def buscar_noticias(query: str) -> str:
    """Busca NOTICIAS recientes sobre un tema. Usa esta en vez de buscar_internet cuando pregunten por noticias, actualidad o qué está pasando.
    IMPORTANTE: Genera un query optimizado, NO copies el texto literal del usuario.
    
    Args:
        query: Query de búsqueda de noticias optimizado
    """
    return search.search_news(query)

@tool  
def crear_suscripcion(tema: str) -> str:
    """Crea una alerta diaria. Todos los días a las 9 AM el usuario recibirá un resumen completo sobre el tema.
    
    Args:
        tema: Tema a seguir (ej: 'IPSA', 'Precio del cobre', 'Bitcoin', 'Noticias Chile')
    """
    return "PENDING_USER_PHONE"

@tool
def listar_suscripciones() -> str:
    """Muestra todas las suscripciones/alertas diarias activas del usuario."""
    return "PENDING_USER_PHONE"

@tool
def cancelar_suscripcion(tema: str) -> str:
    """Cancela una alerta diaria.
    
    Args:
        tema: Tema de la suscripción a cancelar
    """
    return "PENDING_USER_PHONE"

@tool
def recordar_en_fecha(fecha_hora_iso: str, texto: str) -> str:
    """Programa un recordatorio para una fecha y hora ESPECÍFICA.
    
    REGLAS CRÍTICAS:
    - Calcula la fecha/hora EXACTA basándote en la hora actual
    - Si dice "mañana a las 9", calcula la fecha de mañana y pon 09:00:00-04:00
    - Si dice "en 2 horas", suma 2 horas a la hora actual
    - Si dice "el viernes a las 15:00", busca el próximo viernes
    - SIEMPRE incluye la timezone -04:00 (Chile)
    
    Args:
        fecha_hora_iso: Cuándo enviar el recordatorio en ISO 8601 (ej: '2026-04-15T09:00:00-04:00')
        texto: Qué recordarle al usuario
    """
    return "PENDING_USER_PHONE"


# Bind tools
tools = [
    registrar_gasto, consultar_gastos,
    programar_evento, consultar_calendario,
    guardar_memoria, consultar_memoria,
    buscar_internet, buscar_noticias,
    crear_suscripcion, listar_suscripciones, cancelar_suscripcion,
    recordar_en_fecha
]
llm_with_tools = llm.bind_tools(tools)


# ==================== SYSTEM PROMPT ====================

system_prompt = """Eres el Asistente Personal de Diego. Eres su segundo cerebro digital vía WhatsApp.
Sé conciso, amigable, directo y usa emojis donde aporten valor.

═══════════════════════════════════════════════
🔴 REGLAS ABSOLUTAS - EJECUTAR SIN PREGUNTAR 🔴
═══════════════════════════════════════════════

1. CUANDO EL USUARIO PIDA ALGO, HAZLO DE INMEDIATO. No preguntes confirmación si tienes la info mínima.
2. Si dice "recuérdame mañana a las 9" → USA recordar_en_fecha con la fecha EXACTA de mañana a las 09:00:00-04:00
3. Si dice "agenda una reunión el viernes a las 3" → USA programar_evento con la fecha del próximo viernes a las 15:00:00-04:00
4. NUNCA respondas "¿quieres que lo agende?" si ya tienes la información. HAZLO.

═══════════════════════════════════════════════
📅 REGLAS DE CALENDARIO Y RECORDATORIOS
═══════════════════════════════════════════════

CÁLCULO DE FECHAS - ESTO ES CRÍTICO:
- "mañana" = fecha de hoy + 1 día
- "pasado mañana" = fecha de hoy + 2 días
- "el lunes" = el próximo lunes (si hoy es lunes, el de la próxima semana)
- "en una hora" = hora actual + 1 hora
- "en 30 minutos" = hora actual + 30 minutos

FORMATO OBLIGATORIO para fechas: YYYY-MM-DDTHH:MM:SS-04:00 (timezone Chile)

RECORDATORIOS vs EVENTOS:
- "Recuérdame X" → usa recordar_en_fecha (es un aviso por WhatsApp)
- "Agenda X" / "Pon en el calendario X" → usa programar_evento (crea evento en Google Calendar + recordatorio)

Cuando confirmes un evento o recordatorio, responde de forma natural y concisa. Ejemplo:
"Listo! Agendé tu reunión para el 15/04 a las 15:00. Te avisaré 10 minutos antes."

═══════════════════════════════════════════════
🔍 REGLAS DE BÚSQUEDA EN INTERNET
═══════════════════════════════════════════════

NUNCA busques el texto LITERAL del usuario. SIEMPRE optimiza el query:

❌ INCORRECTO: buscar_internet("cómo va el dólar")
✅ CORRECTO: buscar_internet("cotización dólar peso chileno hoy")

❌ INCORRECTO: buscar_noticias("qué pasa en Chile")  
✅ CORRECTO: buscar_noticias("Chile noticias principales hoy")

❌ INCORRECTO: buscar_internet("cuánto cuesta un PS5")
✅ CORRECTO: buscar_internet("precio PlayStation 5 Chile 2026 tiendas")

Para preguntas de ACTUALIDAD/NOTICIAS → usa buscar_noticias
Para preguntas de INFORMACIÓN GENERAL → usa buscar_internet

Cuando presentes resultados de búsqueda:
- Resume los puntos más relevantes
- Incluye datos numéricos si los hay
- Menciona fuentes cuando sea útil
- NO copies los resultados tal cual, sintetiza

═══════════════════════════════════════════════
💰 REGLAS DE FINANZAS  
═══════════════════════════════════════════════
- Moneda: CLP (pesos chilenos) por defecto
- Si dice "gasté 15 lucas en el super", registra monto=15000, categoria=Supermercado

═══════════════════════════════════════════════
📍 CONTEXTO
═══════════════════════════════════════════════
- País: Chile
- Timezone: America/Santiago (-04:00)
- Idioma: Español chileno
"""

# ==================== HISTORIAL ====================

# Diccionario simple en memoria para el historial de conversaciones por usuario
# En producción, usar Redis o SQL
chat_history = {}


# ==================== PROCESAMIENTO PRINCIPAL ====================

async def agent_process(text: str, phone_number: str) -> str:
    """Procesa un mensaje del usuario y retorna la respuesta del agente."""
    
    # Obtener o inicializar historial del usuario
    if phone_number not in chat_history:
        chat_history[phone_number] = []
    
    # Limitar historial a los últimos 10 mensajes para no exceder tokens
    history = chat_history[phone_number][-10:]
    
    # Obtener hora actual en Chile con información completa
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    
    # Mapeo de días en español
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
    
    fecha_context = (
        f"Fecha actual: {dia_semana}, {ahora.day} de {mes} de {ahora.year}\n"
        f"Hora actual: {ahora.strftime('%H:%M:%S')}\n"
        f"Timezone: America/Santiago (UTC-04:00)\n"
        f"El 'mañana' sería: {(ahora + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}\n"
        f"ISO actual: {ahora.isoformat()}"
    )

    system_content = system_prompt + f"\n\n{fecha_context}\nTeléfono del usuario: {phone_number}"
    
    system_msg = SystemMessage(content=system_content)
    user_msg = HumanMessage(content=text)
    
    messages = [system_msg] + history + [user_msg]
    
    try:
        response = llm_with_tools.invoke(messages)
        
        # Guardar mensaje del usuario en el historial
        chat_history[phone_number].append(user_msg)
        
        # Si el LLM decide usar herramientas
        max_iterations = 5  # Evitar loops infinitos
        iteration = 0
        
        while response.tool_calls and iteration < max_iterations:
            iteration += 1
            
            # Guardar la respuesta del asistente (con tool_calls) en el historial
            chat_history[phone_number].append(response)
            messages.append(response)
            
            tool_results_summary = []
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                logger.info(f"Ejecutando herramienta: {tool_name} con args: {tool_args}")
                
                # Ejecutar herramienta
                result_str = execute_tool(tool_name, tool_args, phone_number)
                
                logger.info(f"Resultado de {tool_name}: {result_str[:200]}...")
                
                tool_results_summary.append(f"{tool_name}: {result_str}")
                
                # Crear mensaje de resultado
                tool_msg = ToolMessage(
                    content=result_str,
                    tool_call_id=tool_call["id"]
                )
                messages.append(tool_msg)
                chat_history[phone_number].append(tool_msg)
            
            # Invocar al LLM de nuevo con los resultados
            try:
                response = llm_with_tools.invoke(messages)
            except Exception as e:
                # Groq a veces falla al generar la respuesta final después de tool calls
                # En ese caso, construimos una respuesta manual con los resultados
                logger.warning(f"Error en segunda invocación del LLM (recuperando): {e}")
                combined = "\n".join(tool_results_summary)
                response = AIMessage(content=combined)
        
        # Guardar respuesta final
        chat_history[phone_number].append(response)
        
        # Mantener historial corto
        chat_history[phone_number] = chat_history[phone_number][-20:]
        
        return response.content
    except Exception as e:
        logger.error(f"Error en agent_process: {e}", exc_info=True)
        return f"⚠️ Ups, ocurrió un error procesando tu mensaje. Intenta de nuevo. ({str(e)[:100]})"


# ==================== EJECUCIÓN DE HERRAMIENTAS ====================

def execute_tool(name: str, args: dict, phone_number: str) -> str:
    """Ejecuta una herramienta y retorna el resultado como string."""
    
    def safe_float(v):
        try: return float(str(v).replace('"', '').replace('$', '').replace(',', '').replace('.', '').strip())
        except: return 0.0

    def execute_calendar_event(a):
        """Crea evento en calendario y programa recordatorio si se especifica."""
        # 1. Crear evento en Google Calendar
        result = google_api.add_calendar_event(a['titulo'], a['inicio_iso'], a['fin_iso'])
        
        # 2. Programar recordatorio si se especificó
        recordatorio_iso = a.get('recordatorio_iso', '')
        if recordatorio_iso and recordatorio_iso.strip():
            try:
                reminder_result = scheduler.add_reminder_at_datetime(
                    recordatorio_iso, 
                    a['titulo'], 
                    phone_number,
                    event_time_iso=a['inicio_iso']
                )
                result += f"\n{reminder_result}"
            except Exception as e:
                logger.error(f"Error programando recordatorio del evento: {e}")
                result += f"\n⚠️ El evento se creó pero hubo un error con el recordatorio: {e}"
        
        return result

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
        "programar_evento": lambda a: execute_calendar_event(a),
        "consultar_calendario": lambda a: execute_query_calendar(a),
        "guardar_memoria": lambda a: google_api.save_memory(a['categoria'], a['detalle']),
        "consultar_memoria": lambda a: google_api.search_memory(a['consulta']),
        "buscar_internet": lambda a: search.search_web(a['query']),
        "buscar_noticias": lambda a: search.search_news(a['query']),
        "crear_suscripcion": lambda a: scheduler.add_subscription(a['tema'], "0 9 * * *", phone_number),
        "listar_suscripciones": lambda a: scheduler.list_subscriptions(phone_number),
        "cancelar_suscripcion": lambda a: scheduler.remove_subscription(a['tema'], phone_number),
        "recordar_en_fecha": lambda a: scheduler.add_reminder_at_datetime(
            a['fecha_hora_iso'], a['texto'], phone_number
        ),
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
