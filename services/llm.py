import httpx
import config
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
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
def cancelar_suscripcion(tema: str, telefono: str) -> str:
    """Cancela una alerta recurrente previamente suscrita."""
    return scheduler.remove_subscription(tema, telefono)

# Bind tools
tools = [registrar_gasto, programar_evento, guardar_memoria, consultar_memoria, buscar_internet, crear_suscripcion, cancelar_suscripcion]
llm_with_tools = llm.bind_tools(tools)

system_prompt = """Eres el Asistente Personal de Vida (Personal AI OS) del usuario.
Tu interfaz es WhatsApp. Sé conciso, amigable y directo. (Usa emojis donde aporte).
Estamos en Chile (considera esto para horarios, moneda CLP y contexto).

Tienes acceso a herramientas para:
1. Finanzas (registrar gastos)
2. Calendario (agendar en Google Calendar)
3. Memoria/Relaciones (guardar y recordar datos)
4. Búsqueda (Internet)
5. Suscripciones (envíos recurrentes diarios a las 9 AM)

Si la solicitud del usuario requiere usar una herramienta, úsala de inmediato.
Si el usuario te hace una pregunta general, usa buscar_internet si necesitas datos actuales, sino responde directamente.
Si creas una suscripción, asegúrate de pasar el 'telefono' extraido del contexto de la conversación.
"""

async def agent_process(text: str, phone_number: str) -> str:
    """Procesa el mensaje del usuario y decide qué hacer."""
    messages = [
        SystemMessage(content=system_prompt + f"\nEl número de teléfono del usuario actual es {phone_number}."),
        HumanMessage(content=text)
    ]
    
    try:
        response = llm_with_tools.invoke(messages)
        
        # Check if the LLM decided to use a tool
        if response.tool_calls:
            # Procesar llamadas a herramientas
            results = []
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Ejecutar herramienta
                # En un sistema en producción usaríamos AgentExecutor, pero lo hacemos directo por simplicidad
                result_str = execute_tool(tool_name, tool_args)
                results.append(result_str)
            
            # Devolver reporte al usuario
            return "\n".join(results)
        else:
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
