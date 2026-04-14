"""Test: crear evento en el calendario de Diego y verificar que aparece"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.google_api import calendar_service, CALENDAR_ID

# Crear un evento de prueba
event = {
    'summary': '🧪 TEST AGENTE - Borrar este evento',
    'start': {
        'dateTime': '2026-04-14T08:00:00-04:00',
        'timeZone': 'America/Santiago',
    },
    'end': {
        'dateTime': '2026-04-14T08:30:00-04:00',
        'timeZone': 'America/Santiago',
    },
}

print(f"Intentando crear evento en: {CALENDAR_ID}")
try:
    created = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    print(f"EXITO! Evento creado: {created.get('summary')}")
    print(f"Link: {created.get('htmlLink')}")
    print(f"ID: {created.get('id')}")
    
    # Ahora verificar que se puede leer
    print("\nVerificando que se puede leer...")
    ev = calendar_service.events().get(calendarId=CALENDAR_ID, eventId=created['id']).execute()
    print(f"Leido: {ev.get('summary')} - {ev['start']['dateTime']}")
    
    # Borrar evento de prueba
    print("\nBorrando evento de prueba...")
    calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=created['id']).execute()
    print("Evento borrado correctamente.")
    
except Exception as e:
    print(f"ERROR: {e}")
