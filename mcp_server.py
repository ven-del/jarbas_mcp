import os
import sys
from dotenv import load_dotenv
from rag_utils import RAGEngine
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Servidor de MCP do Jarbas", "0.1")

arquivos_pdf = [
    "docs/Ebook Apis Llm.pdf",
    "docs/Ebook Aplicacoes RAG Avaliacao.pdf",
    "docs/Ebook IA Etica.pdf",
    "docs/Ebook IA Generativa.pdf",
    "docs/Ebook MCP Model Context Protocol.pdf",
    "docs/Ebook Prompt Engineering.pdf",
    "docs/Ebook RAG Contextual.pdf",
    "docs/Ebook Vetorizacao Embeddings.pdf",
    "docs/Guia Rápido LangSmith.pdf",
]

print(" Carregando RAG Engine", file=sys.stderr)
rag_engine = RAGEngine(pdf_paths=arquivos_pdf)
print(" RAG Engine carregada com sucesso", file=sys.stderr)

@mcp.tool()
def consultar_documentacao(pergunta: str) -> str:
    try:
        contexto = rag_engine.buscar_contexto(pergunta)
        if not contexto:
            return "Desculpe, não consegui encontrar informações relevantes nos documentos."
        return contexto
    except Exception as e:
        return f"Erro ao buscar contexto: {str(e)}"
    
if __name__ == "__main__":
    mcp.run()