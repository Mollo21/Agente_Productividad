"""SUPER TEST FINAL: Validación de todas las herramientas conectadas"""
import asyncio, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import llm

async def test_util(msg):
    print(f"\n--- Probando: {msg} ---")
    response = await llm.agent_process(msg, "56912345678")
    print(f"Respuesta: {response[:150]}...")
    return response

async def main():
    print("🚀 INICIANDO SUPER TEST DE VALIDACIÓN FINAL")
    
    # 1. Probar Finanzas
    await test_util("Registra un gasto de 5000 pesos en sushi")
    
    # 2. Probar Memoria
    await test_util("Recuerda que mis llaves están en el cajón de la entrada")
    await test_util("¿Dónde están mis llaves?")
    
    # 3. Probar Calendario (Todo el día)
    await test_util("Recuérdame el 15 el cumpleaños de mi mamá")
    
    # 4. Probar Calendario (Con hora)
    await test_util("Agenda una reunión hoy a las 23:00")
    
    print("\n✅ SUPER TEST FINALIZADO.")

if __name__ == "__main__":
    asyncio.run(main())
