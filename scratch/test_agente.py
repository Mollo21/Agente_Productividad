"""
Test completo del agente WhatsApp - Prueba todos los escenarios problemáticos.

Ejecutar desde el directorio raíz del proyecto:
  python scratch/test_agente.py
"""
import asyncio
import os
import sys
import io

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Añadir el directorio padre al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import llm


# ==================== CASOS DE PRUEBA ====================
test_cases = [
    # --- RECORDATORIOS (el problema principal) ---
    {
        "name": "Recordatorio mañana a las 9",
        "input": "Recuérdame mañana a las 9 que tengo que ir al doctor",
        "expected": "Debe usar recordar_en_fecha con la fecha de mañana a las 09:00:00-04:00"
    },
    {
        "name": "Recordatorio en 30 minutos",
        "input": "Avísame en 30 minutos que tengo que sacar la comida del horno",
        "expected": "Debe usar recordar_en_fecha con la hora actual + 30 min"
    },
    
    # --- CALENDARIO ---
    {
        "name": "Agendar evento",
        "input": "Agenda una reunión el martes a las 15:00 con el equipo de marketing",
        "expected": "Debe usar programar_evento con fecha del próximo martes a las 15:00"
    },
    {
        "name": "Consultar calendario",
        "input": "¿Qué tengo agendado esta semana?",
        "expected": "Debe usar consultar_calendario"
    },
    
    # --- BÚSQUEDAS (el otro problema) ---
    {
        "name": "Búsqueda amplia de noticias",
        "input": "¿Qué está pasando con el dólar?",
        "expected": "Debe usar buscar_noticias con query optimizado como 'cotización dólar Chile hoy'"
    },
    {
        "name": "Búsqueda de tema amplio",
        "input": "Cuéntame las noticias de hoy en Chile",
        "expected": "Debe buscar_noticias con query amplio, NO literal"
    },
    
    # --- SUSCRIPCIONES ---
    {
        "name": "Crear suscripción",
        "input": "Quiero que todos los días me cuentes sobre el precio del cobre",
        "expected": "Debe usar crear_suscripcion con tema 'precio del cobre'"
    },
    
    # --- GASTOS ---
    {
        "name": "Registrar gasto",
        "input": "Gasté 15 lucas en el supermercado Lider",
        "expected": "Debe usar registrar_gasto con monto=15000"
    },
]


async def run_test(test_case: dict, phone: str = "56912345678"):
    """Ejecuta un caso de prueba individual."""
    print(f"\n{'='*60}")
    print(f"📋 TEST: {test_case['name']}")
    print(f"💬 Input: \"{test_case['input']}\"")
    print(f"🎯 Expected: {test_case['expected']}")
    print(f"{'='*60}")
    
    # Interceptar execute_tool para ver qué herramientas se usan
    original_execute_tool = llm.execute_tool
    tools_called = []
    
    def debug_execute_tool(name, args, phone):
        tools_called.append({"name": name, "args": args})
        # Print limpio
        args_str = str(args)
        try:
            args_clean = args_str.encode('ascii', 'ignore').decode('ascii')
        except:
            args_clean = args_str
        print(f"  🔧 TOOL CALL: {name}")
        print(f"     ARGS: {args_clean}")
        
        result = original_execute_tool(name, args, phone)
        try:
            result_clean = result.encode('ascii', 'ignore').decode('ascii')[:200]
        except:
            result_clean = str(result)[:200]
        print(f"     RESULT: {result_clean}")
        return result
    
    llm.execute_tool = debug_execute_tool
    
    try:
        response = await llm.agent_process(test_case['input'], phone)
        
        try:
            response_clean = response.encode('ascii', 'ignore').decode('ascii')
        except:
            response_clean = str(response)
        
        print(f"\n  📤 RESPONSE: {response_clean}")
        
        if not tools_called:
            print(f"\n  ⚠️ WARNING: No se llamó ninguna herramienta!")
        
        print(f"\n  {'✅' if tools_called else '❌'} Tools used: {[t['name'] for t in tools_called]}")
        
        return {
            "name": test_case['name'],
            "passed": len(tools_called) > 0,
            "tools": tools_called,
            "response": response_clean
        }
    except Exception as e:
        print(f"\n  ❌ ERROR: {str(e)}")
        return {
            "name": test_case['name'],
            "passed": False,
            "error": str(e)
        }
    finally:
        llm.execute_tool = original_execute_tool
        # Limpiar historial entre tests
        llm.chat_history.clear()


async def main():
    print("🚀 INICIANDO TESTS DEL AGENTE WHATSAPP")
    print(f"   Modelo: {llm.llm.model_name}")
    print(f"   Tests a ejecutar: {len(test_cases)}")
    
    # Preguntar si quiere correr todos o uno específico
    if len(sys.argv) > 1:
        try:
            idx = int(sys.argv[1])
            results = [await run_test(test_cases[idx])]
        except (ValueError, IndexError):
            # Buscar por nombre
            query = " ".join(sys.argv[1:]).lower()
            matching = [t for t in test_cases if query in t['name'].lower()]
            if matching:
                results = [await run_test(t) for t in matching]
            else:
                print(f"Test no encontrado: {query}")
                return
    else:
        results = []
        for tc in test_cases:
            result = await run_test(tc)
            results.append(result)
    
    # Resumen
    print(f"\n\n{'='*60}")
    print("📊 RESUMEN DE TESTS")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r.get('passed'))
    total = len(results)
    
    for r in results:
        status = "✅" if r.get('passed') else "❌"
        tools_str = ", ".join(t['name'] for t in r.get('tools', [])) if r.get('tools') else "NINGUNA"
        print(f"  {status} {r['name']} → Tools: [{tools_str}]")
    
    print(f"\n  TOTAL: {passed}/{total} tests pasados")


if __name__ == "__main__":
    asyncio.run(main())
