import asyncio
import os
import sys

# Añadir el directorio actual al path para importar servicios
sys.path.append(os.getcwd())

from services import llm

async def main():
    print("--- INICIANDO TEST LOCAL ---")
    user_text = "cuánto llevo de gastos este mes?"
    phone = "123456789"
    
    print(f"Enviando mensaje: '{user_text}'")
    try:
        # Import global objects
        from services import llm
        
        # Override execute_tool to print the execution result
        original_execute_tool = llm.execute_tool
        def debug_execute_tool(name, args, phone):
            res = original_execute_tool(name, args, phone)
            clean_res = res.encode('ascii', 'ignore').decode('ascii')
            print(f">>> TOOL EXECUTION [{name}]: {clean_res}")
            return res
        llm.execute_tool = debug_execute_tool

        response = await llm.agent_process(user_text, phone)
        # Limpiar emojis para evitar errores de consola
        clean_response = response.encode('ascii', 'ignore').decode('ascii')
        print(f"\nRespuesta del agente (sin emojis): {clean_response}")
    except Exception as e:
        print(f"\nERROR DETECTADO: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
