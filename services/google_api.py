import os
import json
import tempfile
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import config
import datetime
import pytz
import dateutil.parser
import logging

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar'
]

CALENDAR_ID = 'diegomollo65@gmail.com'

def get_google_services():
    """
    Inicializa servicios de Google.
    Soporta DOS métodos de autenticación:
    1. Archivo credentials.json local (desarrollo)
    2. Variable de entorno GOOGLE_CREDENTIALS_JSON (producción/Render)
    """
    creds = None
    
    # Método 1: Variable de entorno con JSON completo (para Render/producción)
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_creds_json:
        try:
            creds_dict = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            logger.info("Google credentials cargadas desde variable de entorno GOOGLE_CREDENTIALS_JSON")
        except Exception as e:
            logger.error(f"Error parseando GOOGLE_CREDENTIALS_JSON: {e}")
    
    # Método 2: Archivo local (para desarrollo)
    if not creds:
        creds_path = config.GOOGLE_CREDENTIALS_FILE
        if not os.path.isabs(creds_path):
            possible_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), creds_path)
            if os.path.exists(possible_path):
                creds_path = possible_path

        if os.path.exists(creds_path):
            try:
                creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
                logger.info(f"Google credentials cargadas desde archivo: {creds_path}")
            except Exception as e:
                logger.error(f"Error leyendo archivo de credenciales: {e}")
        else:
            logger.warning(f"Archivo de credenciales no encontrado: {creds_path}")
    
    if not creds:
        logger.error("NO se pudieron cargar credenciales de Google. Calendar y Sheets NO funcionarán.")
        return None, None
    
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        calendar_service = build('calendar', 'v3', credentials=creds)
        logger.info("Servicios de Google Sheets y Calendar inicializados correctamente.")
        return sheets_service, calendar_service
    except Exception as e:
        logger.error(f"Error construyendo servicios de Google: {e}")
        return None, None

sheets_service, calendar_service = get_google_services()

# --- FINANZAS ---
def log_expense(amount: float, category: str, description: str):
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "❌ No se ha configurado Google Sheets."
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
        return f"❌ Error guardando en Sheets: {e}"

def get_expenses(mes_str: str = ""):
    """Obtiene un resumen de los gastos recientes."""
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "❌ No se ha configurado Google Sheets."
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Finanzas!A:D"
        ).execute()
        rows = result.get('values', [])
        if not rows:
            return "No tienes gastos registrados."
        
        if rows and rows[0][0].lower() == 'fecha':
            rows = rows[1:]

        if mes_str:
            matches = [r for r in rows if mes_str.lower() in str(r).lower()]
        else:
            matches = rows[-20:]
            
        if not matches:
            return f"No hay gastos para la búsqueda: {mes_str}"

        lines = [f"📅 {r[0][:10]} | 💰 ${r[1]} | 🟢 {r[2]} | 📝 {r[3] if len(r)>3 else ''}" for r in matches]
        
        total = 0.0
        for r in matches:
            try: total += float(str(r[1]).replace(',', '').replace('$', '').strip())
            except: pass
            
        return f"📊 *Resumen de Gastos*\nTotal acumulado en este reporte: ${total:,.0f}\n\n" + "\n".join(lines)
    except Exception as e:
        return f"❌ Error leyendo gastos: {e}"

# --- CALENDARIO ---
def add_calendar_event(summary: str, start_time: str, end_time: str, all_day: bool = False):
    """Crea un evento en Google Calendar. 
    
    Si all_day=True, crea un evento de día completo (solo usa la fecha, no la hora).
    start_time y end_time deben ser ISO format.
    """
    if not calendar_service:
        return "❌ ERROR_CALENDAR: No se ha configurado Google Calendar. Verifica que GOOGLE_CREDENTIALS_JSON esté configurado en Render."
    
    if all_day:
        # Evento de día completo: usar solo la fecha (YYYY-MM-DD)
        try:
            start_date = dateutil.parser.isoparse(start_time).strftime('%Y-%m-%d')
            # Para all-day, el end_date debe ser el día SIGUIENTE
            end_dt = dateutil.parser.isoparse(start_time) + datetime.timedelta(days=1)
            end_date = end_dt.strftime('%Y-%m-%d')
        except:
            start_date = start_time[:10]
            end_date = start_time[:10]
        
        event = {
            'summary': summary,
            'start': {'date': start_date},
            'end': {'date': end_date},
        }
    else:
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
        created = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        link = created.get('htmlLink', '')
        logger.info(f"Evento creado exitosamente: '{summary}' - Link: {link}")
        return f"✅ CALENDAR_OK: Evento '{summary}' creado. Link: {link}"
    except Exception as e:
        logger.error(f"Error creando evento en Calendar: {e}")
        return f"❌ ERROR_CALENDAR: {e}"


def get_calendar_events(time_min: str, time_max: str) -> str:
    """Obtiene eventos del calendario entre dos fechas ISO."""
    if not calendar_service:
        return "❌ No se ha configurado Google Calendar."
    
    try:
        dt_min = dateutil.parser.isoparse(time_min)
        dt_max = dateutil.parser.isoparse(time_max)
        
        tz = pytz.timezone(config.TIMEZONE)
        if dt_min.tzinfo is None:
            dt_min = tz.localize(dt_min)
        if dt_max.tzinfo is None:
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
                if 'T' in start:
                    fecha_str = start_dt.strftime('%d/%m/%Y %H:%M')
                else:
                    fecha_str = start_dt.strftime('%d/%m/%Y') + " (todo el día)"
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
        return "❌ No se ha configurado Google Sheets."
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
        return f"❌ Error guardando memoria: {e}"

def search_memory(query: str):
    """Busca en todo el sheet de memoria algo relacionado."""
    if not sheets_service or not config.GOOGLE_SHEETS_ID:
        return "❌ No se ha configurado Google Sheets."
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Memoria!A:C"
        ).execute()
        rows = result.get('values', [])
        matches = [f"[{r[0]}] {r[1]}: {r[2]}" for r in rows if query.lower() in str(r).lower()]
        if matches:
            return "Encontré esto:\n" + "\n".join(matches)
        return "No encontré nada relacionado a eso en tu memoria."
    except Exception as e:
        return f"❌ Error consultando memoria: {e}"
