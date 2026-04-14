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
    1. Archivo credentials.json (local)
    2. Variable env GOOGLE_CREDENTIALS_JSON (Render)
    """
    creds = None
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_creds_json:
        try:
            creds_dict = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            logger.error(f"Error parseando GOOGLE_CREDENTIALS_JSON: {e}")
    
    if not creds:
        creds_path = config.GOOGLE_CREDENTIALS_FILE
        if os.path.exists(creds_path):
            try:
                creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
            except Exception as e:
                logger.error(f"Error leyendo archivo de credenciales: {e}")
    
def ensure_sheet_exists(sheet_name: str, headers: list):
    """Verifica si una pestaña existe, si no, la crea con cabeceras."""
    if not sheets_service: return
    try:
        spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=config.GOOGLE_SHEETS_ID).execute()
        sheets = [s.get('properties', {}).get('title') for s in spreadsheet.get('sheets', [])]
        
        if sheet_name not in sheets:
            logger.info(f"Creando pestaña faltante: {sheet_name}")
            body = {'requests': [{'addSheet': {'properties': {'title': sheet_name}}}]}
            sheets_service.spreadsheets().batchUpdate(spreadsheetId=config.GOOGLE_SHEETS_ID, body=body).execute()
            
            # Agregar cabeceras
            sheets_service.spreadsheets().values().update(
                spreadsheetId=config.GOOGLE_SHEETS_ID,
                range=f"{sheet_name}!A1",
                valueInputOption="USER_ENTERED",
                body={'values': [headers]}
            ).execute()
    except Exception as e:
        logger.error(f"Error asegurando pestaña {sheet_name}: {e}")

sheets_service, calendar_service = get_google_services()

# --- FINANZAS ---
def log_expense(amount: float, category: str, description: str):
    if not sheets_service or not config.GOOGLE_SHEETS_ID: return "❌ No Sheets"
    ensure_sheet_exists("Finanzas", ["Fecha", "Monto", "Categoria", "Descripcion"])
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values = [[date_str, amount, category, description]]
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID,
            range="Finanzas!A:D",
            valueInputOption="USER_ENTERED",
            body={'values': values}
        ).execute()
        return f"✅ Gasto registrado: ${amount:,.0f} en {category}"
    except Exception as e: return f"❌ Error Sheets: {e}"

def get_expenses(mes_str: str = ""):
    if not sheets_service: return "❌ No Sheets"
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Finanzas!A:D"
        ).execute()
        rows = result.get('values', [])
        if not rows: return "No hay gastos."
        matches = rows[-20:]
        total = sum(float(str(r[1]).replace(',','')) for r in matches if len(r)>1)
        return f"📊 *Resumen Gastos*\nTotal: ${total:,.0f}"
    except: return "Error leyendo gastos."

# --- CALENDARIO ---
def add_calendar_event(summary: str, start_iso: str, end_iso: str, all_day: bool = False):
    if not calendar_service: return "❌ No Calendar"
    if all_day:
        dt = dateutil.parser.isoparse(start_iso)
        event = {
            'summary': summary,
            'start': {'date': dt.strftime('%Y-%m-%d')},
            'end': {'date': (dt + datetime.timedelta(days=1)).strftime('%Y-%m-%d')},
        }
    else:
        event = {
            'summary': summary,
            'start': {'dateTime': start_iso, 'timeZone': config.TIMEZONE},
            'end': {'dateTime': end_iso, 'timeZone': config.TIMEZONE},
        }
    try:
        calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return "✅ CALENDAR_OK"
    except Exception as e: return f"❌ ERROR_CALENDAR: {e}"

def get_calendar_events(time_min: str, time_max: str):
    if not calendar_service: return "❌ No Calendar"
    events = calendar_service.events().list(
        calendarId=CALENDAR_ID, timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy='startTime'
    ).execute().get('items', [])
    if not events: return "No hay eventos."
    return "📋 *Eventos:*\n" + "\n".join([f"• {e.get('summary')}" for e in events])

# --- MEMORIA ---
def save_memory(topic: str, detail: str):
    if not sheets_service: return "❌ No Sheets"
    ensure_sheet_exists("Memoria", ["Fecha", "Tema", "Detalle"])
    values = [[datetime.datetime.now().strftime("%Y-%m-%d"), topic, detail]]
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Memoria!A:C",
            valueInputOption="USER_ENTERED", body={'values': values}
        ).execute()
        return f"✅ Memoria guardada: {topic}"
    except: return "❌ Error guardando memoria."

def search_memory(query: str):
    if not sheets_service: return "❌ No Sheets"
    rows = sheets_service.spreadsheets().values().get(
        spreadsheetId=config.GOOGLE_SHEETS_ID, range="Memoria!A:C"
    ).execute().get('values', [])
    matches = [f"{r[1]}: {r[2]}" for r in rows if query.lower() in str(r).lower()]
    return "\n".join(matches) if matches else "No encontré nada."

# --- SUSCRIPCIONES (Persistencia) ---
def save_subscription(topic: str, hour: int, minute: int, phone_number: str):
    if not sheets_service: return False
    ensure_sheet_exists("Suscripciones", ["Telefono", "Tema", "Hora"])
    values = [[phone_number, topic, f"{hour:02d}:{minute:02d}"]]
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Suscripciones!A:C",
            valueInputOption="USER_ENTERED", body={'values': values}
        ).execute()
        return True
    except: return False

def get_all_subscriptions():
    if not sheets_service: return []
    try:
        rows = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Suscripciones!A:C"
        ).execute().get('values', [])
        return rows[1:] if rows and len(rows)>0 else []
    except: return []

def delete_subscription_sheet(topic: str, phone_number: str):
    if not sheets_service: return False
    try:
        rows = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Suscripciones!A:C"
        ).execute().get('values', [])
        if not rows: return False
        new_rows = [rows[0]]
        deleted = False
        for r in rows[1:]:
            if len(r)>=2 and r[1].lower()==topic.lower() and r[0]==phone_number:
                deleted = True; continue
            new_rows.append(r)
        if deleted:
            sheets_service.spreadsheets().values().clear(spreadsheetId=config.GOOGLE_SHEETS_ID, range="Suscripciones!A:Z").execute()
            sheets_service.spreadsheets().values().update(spreadsheetId=config.GOOGLE_SHEETS_ID, range="Suscripciones!A1", valueInputOption="USER_ENTERED", body={'values': new_rows}).execute()
        return deleted
    except: return False
