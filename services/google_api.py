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
    """
    creds = None
    google_creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    
    if google_creds_json:
        try:
            creds_dict = json.loads(google_creds_json)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            logger.info("Credenciales cargadas desde ENV_VAR.")
        except Exception as e:
            logger.error(f"Error parseando GOOGLE_CREDENTIALS_JSON: {e}")
    
    if not creds:
        creds_path = config.GOOGLE_CREDENTIALS_FILE
        if os.path.exists(creds_path):
            try:
                creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
                logger.info("Credenciales cargadas desde archivo local.")
            except Exception as e:
                logger.error(f"Error leyendo archivo de credenciales: {e}")
    
    if not creds:
        logger.error("NO se pudieron cargar credenciales de Google.")
        return None, None
    
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        calendar_service = build('calendar', 'v3', credentials=creds)
        return sheets_service, calendar_service
    except Exception as e:
        logger.error(f"Error construyendo servicios: {e}")
        return None, None

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

# Inicialización GLOBAL de servicios
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

def get_expenses(mes_busqueda: str = ""):
    if not sheets_service or not config.GOOGLE_SHEETS_ID: return "❌ No Sheets"
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Finanzas!A:D"
        ).execute()
        rows = result.get('values', [])
        if not rows or len(rows) <= 1: return "No hay gastos registrados aún en tu planilla."
        
        # Saltamos cabeceras y nos quedamos con los datos
        data_rows = rows[1:]
        
        # Determinar mes y año a buscar (Chile Time)
        tz = pytz.timezone(config.TIMEZONE)
        ahora = datetime.datetime.now(tz)
        target_month = ahora.month
        target_year = ahora.year
        
        meses_map = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
            "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }
        
        if mes_busqueda:
            mes_busqueda_lower = mes_busqueda.lower()
            for m_name, m_num in meses_map.items():
                if m_name in mes_busqueda_lower:
                    target_month = m_num
                    break
        
        filtered_rows = []
        for r in data_rows:
            if len(r) < 2: continue
            try:
                # La fecha está en r[0] como "YYYY-MM-DD HH:MM:SS" o similar
                # Intentamos parsear la fecha del registro
                date_dt = dateutil.parser.parse(r[0])
                if date_dt.month == target_month and date_dt.year == target_year:
                    filtered_rows.append(r)
            except:
                continue
                
        if not filtered_rows:
            mes_nombre = [k for k, v in meses_map.items() if v == target_month][0].capitalize()
            return f"No encontré gastos registrados para el mes de {mes_nombre} {target_year}."
            
        # Agrupar por categoría
        summary = {}
        total_general = 0
        for r in filtered_rows:
            try:
                monto = float(str(r[1]).replace(',','').replace('$','').replace('.','').strip())
                # En Chile a veces el punto es separador de miles, pero float() espera punto como decimal.
                # Si es CLP, usualmente no hay decimales. Tratamos de limpiar lo mejor posible.
                cat = r[2] if len(r) > 2 else "Sin Categoría"
                summary[cat] = summary.get(cat, 0) + monto
                total_general += monto
            except:
                continue
        
        # Formatear respuesta
        nombre_mes_actual = [k for k, v in meses_map.items() if v == target_month][0].capitalize()
        
        msg = f"📊 *Resumen de Gastos - {nombre_mes_actual} {target_year}*\n"
        msg += "══════════════════\n"
        
        # Ordenar categorías por monto (descendente)
        sorted_cats = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        
        for cat, total in sorted_cats:
            msg += f"• *{cat}*: ${total:,.0f}\n"
            
        msg += "══════════════════\n"
        msg += f"💰 *TOTAL MENSUAL: ${total_general:,.0f}*\n"
        msg += "\n¿Te gustaría ver el detalle de algún gasto en específico?"
        
        return msg
    except Exception as e:
        logger.error(f"Error en get_expenses: {e}", exc_info=True)
        return "Hubo un error al leer tu planilla de finanzas. Revisa que el ID sea correcto y tenga permisos."

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
    try:
        events = calendar_service.events().list(
            calendarId=CALENDAR_ID, timeMin=time_min, timeMax=time_max, singleEvents=True, orderBy='startTime'
        ).execute().get('items', [])
        if not events: return "No hay eventos."
        return "📋 *Eventos:*\n" + "\n".join([f"• {e.get('summary')}" for e in events])
    except: return "Error calendario."

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
    try:
        rows = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Memoria!A:C"
        ).execute().get('values', [])
        matches = [f"{r[1]}: {r[2]}" for r in rows if len(r)>2 and query.lower() in str(r).lower()]
        return "\n".join(matches) if matches else "No encontré nada."
    except: return "Error memoria."

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
        return deleted
    except: return False

# --- RECORDATORIOS (One-off) ---
def save_reminder_sheet(phone_number: str, text: str, run_at_iso: str, event_time_iso: str):
    if not sheets_service: return False
    ensure_sheet_exists("Recordatorios", ["Telefono", "Texto", "RunAtISO", "EventTimeISO"])
    values = [[phone_number, text, run_at_iso, event_time_iso]]
    try:
        sheets_service.spreadsheets().values().append(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Recordatorios!A:D",
            valueInputOption="USER_ENTERED", body={'values': values}
        ).execute()
        return True
    except: return False

def get_all_reminders_sheet():
    if not sheets_service: return []
    try:
        rows = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Recordatorios!A:D"
        ).execute().get('values', [])
        return rows[1:] if rows and len(rows)>0 else []
    except: return []

def delete_reminder_sheet(phone_number: str, text: str, run_at_iso: str):
    if not sheets_service: return False
    try:
        rows = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.GOOGLE_SHEETS_ID, range="Recordatorios!A:D"
        ).execute().get('values', [])
        if not rows: return False
        
        new_rows = [rows[0]]
        deleted = False
        for r in rows[1:]:
            if len(r) >= 3 and r[0] == phone_number and r[1] == text and r[2] == run_at_iso:
                deleted = True
                continue
            new_rows.append(r)
            
        if deleted:
            sheets_service.spreadsheets().values().clear(spreadsheetId=config.GOOGLE_SHEETS_ID, range="Recordatorios!A:Z").execute()
            sheets_service.spreadsheets().values().update(
                spreadsheetId=config.GOOGLE_SHEETS_ID, range="Recordatorios!A1", 
                valueInputOption="USER_ENTERED", body={'values': new_rows}
            ).execute()
        return deleted
    except Exception as e:
        logger.error(f"Error borrando recordatorio: {e}")
        return False
