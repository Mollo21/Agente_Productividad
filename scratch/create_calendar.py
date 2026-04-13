import os
import sys

sys.path.append(os.getcwd())
from services import google_api

def share_primary_calendar():
    email_to_share = "diegomollo65@gmail.com"
    rule = {
        'scope': {
            'type': 'user',
            'value': email_to_share,
        },
        'role': 'owner' # Dar permisos completos al usuario
    }

    try:
        # Compartimos el calendario 'primary' de la cuenta de servicio con ti
        created_rule = google_api.calendar_service.acl().insert(calendarId='primary', body=rule).execute()
        print(f"Éxito: Calendario compartido con {email_to_share}. Regla ID: {created_rule['id']}")
    except Exception as e:
        print(f"Error al compartir el calendario: {e}")

if __name__ == "__main__":
    share_primary_calendar()
