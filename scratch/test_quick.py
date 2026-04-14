"""Test los casos EXACTOS que fallaron en producción"""
import asyncio, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import llm

async def test(msg, phone="56912345678"):
    print(f"\n{'='*60}")
    print(f"💬 USUARIO: \"{msg}\"")
    print(f"{'='*60}")
    
    original = llm.execute_tool
    def debug(name, args, phone):
        print(f"\n  🔧 TOOL: {name}")
        for k,v in args.items():
            print(f"    {k}: {v}")
        result = original(name, args, phone)
        # Mostrar si el calendar funcionó
        if "CALENDAR_OK" in result or "ERROR_CALENDAR" in result:
            if "CALENDAR_OK" in result:
                print(f"    ✅ CALENDAR: OK")
            else:
                print(f"    ❌ CALENDAR: FAILED")
        return result
    llm.execute_tool = debug
    
    response = await llm.agent_process(msg, phone)
    print(f"\n📤 RESPUESTA FINAL:\n{response}")
    
    llm.execute_tool = original
    llm.chat_history.clear()

async def main():
    print("🧪 TESTING CASOS QUE FALLARON EN PRODUCCIÓN")
    
    # Caso 1: El que falló exacto
    await test("Recuérdame el día 15 cumpleaños tomy")
    
    # Caso 2: Otro sin hora
    await test("el 20 tengo prueba de derecho")
    
    # Caso 3: Con hora (debe seguir funcionando)
    await test("mañana 9pm hacer tarea")

asyncio.run(main())
