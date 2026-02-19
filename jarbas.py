import os
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
    env=os.environ
)

with open ('jarbas.md', 'r', encoding='utf-8') as f:
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

async def consultar_servidor_mcp (pergunta: str):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            result = await session.call_tool(
                "consultar_documentacao",
                arguments={"pergunta": pergunta}
            )

            if result.content and len(result.content) >0:
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
        response = chat.send_message(mensagem_com_contexto)
        return response.text
    except Exception as e:
        return f"Erro: {str(e)}"

demo = gr.ChatInterface(
    fn=gerar_resposta,
    title='Jarbas - O Amado Assistente Virtual',
    description='Versão do nosso querido com o Gradio, agora com RAG!'
)

if __name__ == "__main__":
    demo.launch(share=True)