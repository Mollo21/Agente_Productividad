# Asistente Personal de WhatsApp (AI OS)

Agente 100% gratuito basado en la API de Meta WhatsApp Cloud y Groq (Llama 3 / Whisper). Funciona como un segundo cerebro, gestor financiero, de relaciones y envía suscripciones programadas.

## 🛠️ Tecnologías Utilizadas
*   **LLM & Rápidez:** [Groq](https://groq.com) (Llama 3 70B & Whisper).
*   **WhatsApp:** API Oficial de Nube de WhatsApp de Meta (Gratis).
*   **Base de Datos y Finanzas:** Google Sheets & Google Calendar.
*   **Web Search:** DuckDuckGo Web Search.
*   **Backend:** Python con FastAPI y Langchain.

## 🚀 Guía de Instalación (Despliegue 100% Gratis)

### 1. Obtener API Keys
1.  **Groq:** Ve a [console.groq.com](https://console.groq.com) y crea una API Key gratuita.
2.  **WhatsApp Cloud API:**
    *   Ve a [Meta for Developers](https://developers.facebook.com/).
    *   Crea una App de tipo "Business".
    *   Añade el producto "WhatsApp".
    *   Usa el Número de Prueba (o registra el tuyo). Obtén el `WHATSAPP_TOKEN` temporal y el `PHONE_NUMBER_ID`.
3.  **Google Cloud (Sheets & Calendar):**
    *   Ve a [Google Cloud Console](https://console.cloud.google.com/).
    *   Habilita "Google Sheets API" y "Google Calendar API".
    *   Crea Credenciales de "Cuenta de Servicio" (Service Account).
    *   Descarga el archivo JSON y guárdalo como `credentials.json` en la raíz del proyecto.
    *   Crea un Google Sheet en tu cuenta, ponle unas pestañas llamadas `Finanzas` (A: Fecha, B: Monto, C: Categoria, D: Descripcion) y `Memoria`.
    *   **Importante:** Comparte ese Sheet dandole permisos de Editor al correo electrónico de tu cuenta de servicio. Copia el ID del Sheet (está en la URL).

### 2. Configuración Local
1. Clona el repositorio e instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Renombra `.env.example` a `.env` y pega tus llaves ahí.

### 3. Exponer el servidor (Para conectar con WhatsApp)
Para que Meta envíe los mensajes a tu máquina local, usa un túnel gratis como **Ngrok** o **Cloudflare Tunnels**.
```bash
# Iniciar backend
python main.py

# En otra terminal, exponer puerto 8000
ngrok http 8000
```
* Copia la URL de Ngrok (ej: `https://abcd.ngrok-free.app/webhook`).
* Ve a Meta Developers > WhatsApp > Configuración -> Webhooks.
* Pega la URL y el Verify Token (`mi_token_secreto_whatsapp`).
* Suscríbete al campo `messages`.

### 4. Despliegue en la Nube (Gratis y 24/7)
Para no tener tu PC encendido:
1. Sube este código a un repositorio privado de **GitHub**.
2. Entra a **Render** (render.com) o **Railway** (railway.app).
3. Crea un "Web Service", conéctalo a tu GitHub.
4. Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Añade todas las variables de entorno de tu `.env` directamente en el panel de Secrets de Render/Railway.
6. Copia tu contenido de `credentials.json` en Render usando "Secret Files".
7. Actualiza la URL del Webhook en Meta con tu nueva URL de Render (ej: `https://mi-agente.onrender.com/webhook`).
