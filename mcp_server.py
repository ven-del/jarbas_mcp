import os
import sys
from dotenv import load_dotenv
from rag_utils import RAGEngine
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Servidor de MCP do Jarbas", "0.1")

rag_engine = RAGEngine()  # Instancia global da RAG Engine para evitar recarregamentos desnecessários

def get_rag_engine():
    global rag_engine
    if rag_engine is None:
        print(" Carregando RAG Engine", file=sys.stderr, flush=True)
        rag_engine = RAGEngine()
        print(" RAG Engine carregada com sucesso", file=sys.stderr, flush=True)
    return rag_engine

@mcp.tool()
def consultar_documentacao(pergunta: str) -> str:
    try:
        engine = get_rag_engine()
        contexto = engine.buscar_contexto(pergunta)
        if not contexto:
            return "Desculpe, não consegui encontrar informações relevantes nos documentos."
        return contexto
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Erro ao buscar contexto: {error_detail}", file=sys.stderr, flush=True)
        return f"Erro ao buscar contexto: {str(e)}"
    
if __name__ == "__main__":
    mcp.run()