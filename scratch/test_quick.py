"""Test rápido del caso exacto del usuario"""
import asyncio, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import llm

async def main():
    print("TEST: 'mañana 9pm hacer tarea'")
    print("="*60)
    
    original = llm.execute_tool
    def debug(name, args, phone):
        print(f"  TOOL: {name}")
        for k,v in args.items():
            print(f"    {k}: {v}")
        result = original(name, args, phone)
        return result
    llm.execute_tool = debug
    
    response = await llm.agent_process("mañana 9pm hacer tarea", "56912345678")
    print(f"\nRESPUESTA FINAL:\n{response}")
    
    llm.execute_tool = original
    llm.chat_history.clear()

asyncio.run(main())
