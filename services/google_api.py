import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import config
import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar'
]

CALENDAR_ID = 'diegomollo65@gmail.com'

def get_google_services():
    creds_path = config.GOOGLE_CREDENTIALS_FILE
    # Intentar encontrar el archivo si el path es relativo
    if not os.path.isabs(creds_path):
        # Buscar en el mismo directorio que config.py o el cwd
        possible_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), creds_path)
        if os.path.exists(possible_path):
            creds_path = possible_path

    if not os.path.exists(creds_path):
        logger.error(f"Archivo de credenciales no encontrado: {creds_path}")
        return None, None
    
    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        sheets_service = build('sheets', 'v4', credentials=creds)
        calendar_service = build('calendar', 'v3', credentials=creds)
        return sheets_service, calendar_service
    except Exception as e:
        logger.error(f"Error inicializando servicios de Google: {e}")
        return None, None

sheets_service, calendar_service = get_google_services()

# --- FINANZAS ---
def log_expense(amount: float, category: str, description: str):
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "No se ha configurado Google Sheets."
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values = [[date_str, amount, category, description]]
    body = {'values': values}
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Finanzas!A:D",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return f"✅ Gasto registrado: ${amount:,.0f} en {category} ({description})"
    except Exception as e:
        return f"Error guardando en Sheets: {e}"

def get_expenses(mes_str: str = ""):
    """Obtiene un resumen de los gastos recientes."""
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "No se ha configurado Google Sheets."
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Finanzas!A:D"
        ).execute()
        rows = result.get('values', [])
        if not rows:
            return "No tienes gastos registrados."
        
        # Omitir header si existe ('Fecha', 'Monto', etc)
        if rows and rows[0][0].lower() == 'fecha':
            rows = rows[1:]

        # Si se solicita texto/mes, filtrar
        if mes_str:
            matches = [r for r in rows if mes_str.lower() in str(r).lower()]
        else:
            matches = rows[-20:] # últimos 20
            
        if not matches:
            return f"No hay gastos para la búsqueda: {mes_str}"

        lines = [f"📅 {r[0][:10]} | 💰 ${r[1]} | 🟢 {r[2]} | 📝 {r[3] if len(r)>3 else ''}" for r in matches]
        
        # Tratar de calcular total
        total = 0.0
        for r in matches:
            try: total += float(str(r[1]).replace(',', '').replace('$', '').strip())
            except: pass
            
        return f"📊 *Resumen de Gastos*\nTotal acumulado en este reporte: ${total:,.0f}\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Error leyendo gastos: {e}"

# --- CALENDARIO ---
def add_calendar_event(summary: str, start_time: str, end_time: str):
    """Crea un evento en Google Calendar. start_time y end_time deben ser ISO format."""
    if not calendar_service:
        return "❌ No se ha configurado Google Calendar."
    
    event = {
      'summary': summary,
      'start': {
        'dateTime': start_time,
        'timeZone': config.TIMEZONE,
      },
      'end': {
        'dateTime': end_time,
        'timeZone': config.TIMEZONE,
      },
    }
    try:
        event = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return f"✅ Evento '{summary}' creado en Google Calendar. Link: {event.get('htmlLink')}"
    except Exception as e:
        logger.error(f"Error creando evento en Calendar: {e}")
        return f"❌ Error creando evento: {e}"


def get_calendar_events(time_min: str, time_max: str) -> str:
    """Obtiene eventos del calendario entre dos fechas ISO."""
    if not calendar_service:
        return "❌ No se ha configurado Google Calendar."
    
    try:
        # Asegurar formato correcto para la API
        import dateutil.parser
        dt_min = dateutil.parser.isoparse(time_min)
        dt_max = dateutil.parser.isoparse(time_max)
        
        # La API de Calendar requiere formato RFC3339
        if dt_min.tzinfo is None:
            tz = pytz.timezone(config.TIMEZONE)
            dt_min = tz.localize(dt_min)
        if dt_max.tzinfo is None:
            tz = pytz.timezone(config.TIMEZONE)
            dt_max = tz.localize(dt_max)
        
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=dt_min.isoformat(),
            timeMax=dt_max.isoformat(),
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📅 No tienes eventos programados entre {dt_min.strftime('%d/%m/%Y')} y {dt_max.strftime('%d/%m/%Y')}."
        
        lines = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            try:
                start_dt = dateutil.parser.isoparse(start)
                fecha_str = start_dt.strftime('%d/%m/%Y %H:%M')
            except:
                fecha_str = start
            
            summary = event.get('summary', 'Sin título')
            lines.append(f"• 📅 {fecha_str} — {summary}")
        
        return f"📋 *Tus eventos ({len(events)}):*\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Error consultando calendario: {e}")
        return f"❌ Error consultando calendario: {e}"


# --- SEGUNDO CEREBRO / RELACIONES (En Sheets) ---
def save_memory(topic: str, detail: str):
    """Guarda un hecho o información de una persona."""
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "No se ha configurado Google Sheets."
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    values = [[date_str, topic, detail]]
    body = {'values': values}
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Memoria!A:C",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return f"✅ Memoria guardada bajo '{topic}'"
    except Exception as e:
        return f"Error guardando memoria: {e}"

def search_memory(query: str):
    """Busca en todo el sheet de memoria algo relacionado."""
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "No se ha configurado Google Sheets."
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Memoria!A:C"
        ).execute()
        rows = result.get('values', [])
        # Búsqueda por texto
        matches = [f"[{r[0]}] {r[1]}: {r[2]}" for r in rows if query.lower() in str(r).lower()]
        if matches:
            return "Encontré esto:\n" + "\n".join(matches)
        return "No encontré nada relacionado a eso en tu memoria."
    except Exception as e:
        return f"Error consultando memoria: {e}"
