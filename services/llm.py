import httpx
import config
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from services import google_api, search, scheduler
import json

# Setup del LLM
llm = ChatGroq(
    temperature=0, 
    model_name="meta-llama/llama-4-scout-17b-16e-instruct", # Actualizado a Llama 4 Scout
    api_key=config.GROQ_API_KEY
)

@tool
def registrar_gasto(monto: float, categoria: str, descripcion: str) -> str:
    """Registra un gasto económico. Uso: registrar_gasto(5000, 'Comida', 'Almuerzo McDonald\'s')"""
    return google_api.log_expense(monto, categoria, descripcion)

@tool
def programar_evento(titulo: str, inicio_iso: str, fin_iso: str) -> str:
    """Agenda un evento. Las fechas DEBEN estar en formato ISO 8601 con zona horaria (ej: 2024-05-20T15:00:00-04:00)."""
    return google_api.add_calendar_event(titulo, inicio_iso, fin_iso)

@tool
def guardar_memoria(categoria: str, detalle: str) -> str:
    """Guarda un dato para recordar a futuro o información de un contacto/relación. Ej: categoria='Llaves', detalle='Las dejé en cajón azul' o categoria='Marta', detalle='Le gustan las rosas'."""
    return google_api.save_memory(categoria, detalle)

@tool
def consultar_memoria(consulta: str) -> str:
    """Busca en tu memoria datos guardados previamente o detalles de relaciones."""
    return google_api.search_memory(consulta)

@tool
def buscar_internet(query: str) -> str:
    """Busca información actualizada, noticias o datos de mercado en internet."""
    return search.search_web(query)

@tool
def crear_suscripcion(tema: str, telefono: str) -> str:
    """Crea una alerta recurrente que envía info todos los días a las 9 AM sobre un tema (ej: 'IPSA', 'Precio Cobre'). El telefono es el numero del usuario."""
    return scheduler.add_subscription(tema, "0 9 * * *", telefono)

@tool
def recordar_algo(minutos: int, texto: str, telefono: str) -> str:
    """Programa un recordatorio a futuro. Usa esto si el usuario pide recordarle algo en X minutos o tiempo determinado. 'minutos' debe ser un entero."""
    return scheduler.add_reminder(minutos, texto, telefono)

@tool
def cancelar_suscripcion(tema: str, telefono: str) -> str:
    """Cancela una alerta recurrente previamente suscrita."""
    return scheduler.remove_subscription(tema, telefono)

# Bind tools
tools = [registrar_gasto, programar_evento, guardar_memoria, consultar_memoria, buscar_internet, crear_suscripcion, cancelar_suscripcion, recordar_algo]
llm_with_tools = llm.bind_tools(tools)

system_prompt = """Eres el Asistente Personal de Vida (Personal AI OS) del usuario.
Tu interfaz es WhatsApp. Sé conciso, amigable y directo. (Usa emojis donde aporte).

CRÍTICO: Cuando el usuario te pida recordarle algo o agendar algo, HAZLO DE INMEDIATO usando la herramienta correspondiente. 
NO hagas preguntas de confirmación si tienes la información mínima necesaria. 
Si el usuario dice "recuérdame en 10 minutos tal cosa", simplemente usa 'recordar_algo' y responde confirmando con "Perfecto, te recordaré...".

Estamos en Chile (considera esto para horarios, moneda CLP y contexto).

Tienes acceso a herramientas para:
1. Finanzas (registrar gastos)
2. Calendario (agendar en Google Calendar)
3. Memoria/Relaciones (guardar y recordar datos)
4. Búsqueda (Internet)
5. Suscripciones (envíos recurrentes diarios a las 9 AM)
6. Recordatorios (programar avisos en X minutos)

Si la solicitud del usuario requiere usar una herramienta, úsala de inmediato.
Si el usuario te hace una pregunta general, usa buscar_internet si necesitas datos actuales, sino responde directamente.
Asegúrate de pasar el 'telefono' extraído del contexto a las herramientas que lo requieran.
"""

# Diccionario simple en memoria para el historial de conversaciones por usuario
# En producción, usar Redis o SQL
chat_history = {}

async def agent_process(text: str, phone_number: str) -> str:
    import datetime
    import pytz
    
    # Obtener o inicializar historial del usuario
    if phone_number not in chat_history:
        chat_history[phone_number] = []
    
    # Limitar historial a los últimos 10 mensajes para no exceder tokens
    history = chat_history[phone_number][-10:]
    
    # Obtener hora actual en Chile
    tz = pytz.timezone(config.TIMEZONE)
    ahora = datetime.datetime.now(tz)
    fecha_hora_str = ahora.strftime("%A, %d de %B de %Y, %H:%M:%S")

    system_msg = SystemMessage(content=system_prompt + f"\nLa fecha y hora actual en Chile es: {fecha_hora_str}.\nEl número de teléfono del usuario actual es {phone_number}.")
    user_msg = HumanMessage(content=text)
    
    messages = [system_msg] + history + [user_msg]
    
    try:
        response = llm_with_tools.invoke(messages)
        
        # Guardar mensaje del usuario en el historial
        chat_history[phone_number].append(user_msg)
        
        # Si el LLM decide usar herramientas
        while response.tool_calls:
            # Guardar la respuesta del asistente (con tool_calls) en el historial antes de responder con el resultado
            chat_history[phone_number].append(response)
            messages.append(response)
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Ejecutar herramienta
                result_str = execute_tool(tool_name, tool_args)
                
                # Crear mensaje de resultado de herramienta
                tool_msg = ToolMessage(
                    content=result_str,
                    tool_call_id=tool_call["id"]
                )
                messages.append(tool_msg)
                chat_history[phone_number].append(tool_msg)
            
            # Invocar al LLM de nuevo con los resultados para que genere la respuesta final humana
            response = llm_with_tools.invoke(messages)
            
        # Al final, 'response' contendrá la respuesta textual humana (sin más tool_calls)
        chat_history[phone_number].append(response)
        
        # Mantener historial corto
        chat_history[phone_number] = chat_history[phone_number][-20:]
        
        return response.content
    except Exception as e:
        return f"Ups! Ocurrió un error en mi cerebro... 🧠⚡️ ({str(e)})"

def execute_tool(name: str, args: dict) -> str:
    tool_map = {t.name: t for t in tools}
    if name in tool_map:
        return tool_map[name].invoke(args)
    return "Herramienta no encontrada."

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
