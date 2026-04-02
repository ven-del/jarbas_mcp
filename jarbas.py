import asyncio
import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from fasthtml.common import fast_app, serve
from google import genai
from google.genai import types
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.staticfiles import StaticFiles

from rag_utils import RAGEngine

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
HTML_DIR = ASSETS_DIR / "html"
INDEX_FILE = HTML_DIR / "index.html"
SLIDES_FILE = HTML_DIR / "slides.html"
MATERIAL_FILE = HTML_DIR / "material-complementar.html"
READINGS_FILE = HTML_DIR / "leituras-recomendadas.html"
SYSTEM_PROMPT_FILE = BASE_DIR / "persona.md"
MATERIALS_BUCKET = os.getenv("SUPABASE_MATERIALS_BUCKET", "course-docs")
MATERIALS_FOLDER = os.getenv("SUPABASE_MATERIALS_FOLDER", "pdfs")
MATERIALS_CATEGORIES = {
    "slides",
    "material-complementar",
    "leituras-recomendadas",
}

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

with SYSTEM_PROMPT_FILE.open("r", encoding="utf-8") as file:
    system_instructions = file.read()

genai_client = genai.Client()
generation_config = types.GenerateContentConfig(
    system_instruction=system_instructions,
    temperature=1.3,
    top_p=0.9,
    top_k=50,
    max_output_tokens=2048,
)

rag_engine = RAGEngine()


def _slugify(value):
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _material_title_from_name(file_name):
    return Path(file_name).stem.replace("_", " ").strip()


def _material_category_from_title(title):
    slug = _slugify(title)
    if slug.startswith("ebook-"):
        return "material-complementar"
    if slug.startswith("guia-rapido"):
        return "leituras-recomendadas"
    if slug.startswith("slides-") or slug.startswith("slide-"):
        return "slides"
    return "material-complementar"


def _list_storage_pdf_names():
    raw_items = rag_engine.supabase.storage.from_(MATERIALS_BUCKET).list(
        MATERIALS_FOLDER,
        {
            "limit": 300,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        },
    )

    if isinstance(raw_items, dict) and isinstance(raw_items.get("data"), list):
        raw_items = raw_items["data"]

    pdf_names = []
    for item in raw_items or []:
        name = str(item.get("name", "")).strip()
        if name.lower().endswith(".pdf"):
            pdf_names.append(name)

    return pdf_names


def _build_material_items(category):
    items = []

    for file_name in _list_storage_pdf_names():
        title = _material_title_from_name(file_name)
        if _material_category_from_title(title) != category:
            continue

        items.append(
            {
                "id": _slugify(file_name),
                "title": title,
                "status": "Disponivel",
                "available": True,
                "file_name": file_name,
            }
        )

    items.sort(key=lambda value: value["title"].lower())

    target_count = 4 if not items else ((len(items) + 3) // 4) * 4
    for index in range(target_count - len(items)):
        items.append(
            {
                "id": f"placeholder-{index + 1}",
                "title": "Material em breve",
                "status": "Em breve",
                "available": False,
                "file_name": "",
            }
        )

    return items


def _to_chat_history(history, current_user_message):
    if not isinstance(history, list):
        return []

    normalized = []
    for turn in history[-24:]:
        if not isinstance(turn, dict):
            continue

        role = turn.get("role")
        content = str(turn.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue

        normalized.append((role, content))

    if normalized:
        last_role, last_content = normalized[-1]
        if last_role == "user" and last_content == current_user_message:
            normalized.pop()

    merged = []
    for role, content in normalized:
        sdk_role = "model" if role == "assistant" else "user"
        if merged and merged[-1][0] == sdk_role:
            merged[-1] = (sdk_role, f"{merged[-1][1]}\n\n{content}")
            continue
        merged.append((sdk_role, content))

    return [
        types.Content(role=role, parts=[types.Part.from_text(text=content)])
        for role, content in merged
    ]


def _build_prompt(user_message, context):
    context_text = context.strip() or "Nenhum contexto relevante encontrado na base."

    return f"""
Pergunta do usuario:
{user_message}

Contexto recuperado no RAG:
{context_text}

Instrucoes:
- Responda em portugues do Brasil, mantendo a persona definida no system instruction.
- Priorize o contexto recuperado para responder.
- Se o contexto estiver vazio, informe que nao encontrou na base sem sair do personagem.
"""


def _generate_answer(user_message, context, history):
    chat = genai_client.chats.create(
        model=MODEL_NAME,
        config=generation_config,
        history=_to_chat_history(history, user_message),
    )

    prompt = _build_prompt(user_message, context)
    response = chat.send_message(prompt)
    return (response.text or "").strip()


app, rt = fast_app()
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


@rt("/")
def home():
    return FileResponse(INDEX_FILE)


@rt("/slides")
def slides_page():
    return FileResponse(SLIDES_FILE)


@rt("/material-complementar")
def material_page():
    return FileResponse(MATERIAL_FILE)


@rt("/leituras-recomendadas")
def readings_page():
    return FileResponse(READINGS_FILE)


@rt("/api/materials")
async def materials_api(request: Request):
    category = str(request.query_params.get("category", "")).strip().lower()
    if category not in MATERIALS_CATEGORIES:
        return JSONResponse({"error": "Categoria invalida."}, status_code=400)

    try:
        items = await asyncio.to_thread(_build_material_items, category)
        return JSONResponse({"category": category, "items": items})
    except Exception as exc:
        return JSONResponse(
            {"error": f"Erro ao buscar materiais: {exc}"},
            status_code=500,
        )


@rt("/api/materials/download")
async def download_material_api(request: Request):
    file_name = Path(str(request.query_params.get("file", "")).strip()).name
    if not file_name or not file_name.lower().endswith(".pdf"):
        return JSONResponse({"error": "Arquivo invalido."}, status_code=400)

    storage_path = f"{MATERIALS_FOLDER}/{file_name}"

    try:
        file_bytes = await asyncio.to_thread(
            rag_engine.supabase.storage.from_(MATERIALS_BUCKET).download,
            storage_path,
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Nao foi possivel baixar o arquivo: {exc}"},
            status_code=404,
        )

    if not file_bytes:
        return JSONResponse({"error": "Arquivo nao encontrado."}, status_code=404)

    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@rt("/api/chat", methods=["POST"])
async def chat_api(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Corpo JSON invalido."}, status_code=400)

    user_message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])

    if not user_message:
        return JSONResponse({"error": "Mensagem vazia."}, status_code=400)

    try:
        context = await asyncio.to_thread(rag_engine.buscar_contexto, user_message)
        answer = await asyncio.to_thread(_generate_answer, user_message, context, history)

        if not answer:
            answer = "Nao consegui responder agora. Tente novamente em instantes."

        return JSONResponse(
            {
                "answer": answer,
                "context_found": bool(context.strip()),
            }
        )
    except Exception as exc:
        return JSONResponse(
            {"error": f"Erro ao processar a pergunta: {exc}"},
            status_code=500,
        )


if __name__ == "__main__":
    serve()
