import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el mismo directorio que este archivo
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))

# WhatsApp Cloud API config
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "mi_token_secreto_123")

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Google Config
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID") # Para finanzas y memoria

# Agent Config
TIMEZONE = "America/Santiago"
