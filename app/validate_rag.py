# validate_rag.py
import asyncio
from app.rag import answer_with_rag

async def main():
    print("🔍 Prueba de RAG para Cámara de Comercio de Pamplona\n")
    while True:
        question = input("Pregunta (o 'salir'): ")
        if question.lower() in {"salir", "exit"}:
            break
        print("\n⏳ Generando respuesta...")
        ans = await answer_with_rag(question)
        print("\n💬 Respuesta:")
        print(ans)
        print("\n---")

if __name__ == "__main__":
    asyncio.run(main())
