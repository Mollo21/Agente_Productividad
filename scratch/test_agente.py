import asyncio
import os
import sys

# Añadir el directorio actual al path para importar servicios
sys.path.append(os.getcwd())

from services import llm

async def main():
    print("--- INICIANDO TEST LOCAL ---")
    user_text = "recuerdame en 2 minutos test"
    phone = "123456789"
    
    print(f"Enviando mensaje: '{user_text}'")
    try:
        # Forzar utf-8 en la salida de consola si es posible
        import sys
        import io
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

        response = await llm.agent_process(user_text, phone)
        # Limpiar emojis para evitar errores de consola
        clean_response = response.encode('ascii', 'ignore').decode('ascii')
        print(f"\nRespuesta del agente (sin emojis): {clean_response}")
    except Exception as e:
        print(f"\nERROR DETECTADO: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
