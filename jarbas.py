import os
import asyncio
import gradio as gr
from google import genai
from dotenv import load_dotenv
from google.genai import types
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

load_dotenv()

client = genai.Client()

server_params = StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
    env={**os.environ, "PYTHONUNBUFFERED": "1"}
)

with open('jarbas.md', 'r', encoding='utf-8') as f:
    system_instructions = f.read()

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction=system_instructions,
        temperature=1.7,
        top_p=0.9,
        top_k=50,
        max_output_tokens=2048,
    )
)

# Sessão MCP persistente
_session = None
_stdio_context = None
_session_context = None

async def get_session():
    global _session, _stdio_context, _session_context
    if _session is None:
        _stdio_context = stdio_client(server_params)
        read, write = await _stdio_context.__aenter__()
        _session_context = ClientSession(read, write)
        _session = await _session_context.__aenter__()
        await _session.initialize()
        print("Sessão MCP iniciada.", flush=True)
    return _session

async def cleanup_session():
    global _session, _stdio_context, _session_context
    if _session_context:
        await _session_context.__aexit__(None, None, None)
    if _stdio_context:
        await _stdio_context.__aexit__(None, None, None)
    _session = None
    _stdio_context = None
    _session_context = None

async def consultar_servidor_mcp(pergunta: str):
    session = await get_session()
    result = await session.call_tool(
        "consultar_documentacao",
        arguments={"pergunta": pergunta}
    )
    if result.content and len(result.content) > 0:
        return result.content[0].text
    return "Desculpe, não consegui encontrar informações relevantes nos documentos."

async def gerar_resposta(user_message, chat_history):
    try:
        contexto_encontrado = await consultar_servidor_mcp(user_message)
        mensagem_com_contexto = f"""
        Mensagem do usuário:
        {user_message}
        
        Contexto relevante:        
        {contexto_encontrado}

        Responda à mensagem do usuário utilizando o contexto encontrado, se necessário.
        """
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, chat.send_message, mensagem_com_contexto)
        return response.text
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        # Tentar reconectar em caso de erro de conexão
        if "Connection closed" in error_msg or "McpError" in error_msg:
            print("Tentando reconectar ao servidor MCP...", flush=True)
            await cleanup_session()
            try:
                contexto_encontrado = await consultar_servidor_mcp(user_message)
                mensagem_com_contexto = f"""
                Mensagem do usuário:
                {user_message}
                
                Contexto relevante:        
                {contexto_encontrado}

                Responda à mensagem do usuário utilizando o contexto encontrado, se necessário.
                """
                response = await loop.run_in_executor(None, chat.send_message, mensagem_com_contexto)
                return response.text
            except:
                pass
        return error_msg

demo = gr.ChatInterface(
    fn=gerar_resposta,
    title='Jarbas - O Amado Assistente Virtual',
    description='Versão do nosso querido com o Gradio, agora com RAG!'
)

if __name__ == "__main__":
    demo.launch(share=True)