import asyncio
import mimetypes
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
MATERIALS_ROOT_FOLDER = os.getenv("SUPABASE_MATERIALS_ROOT", "docs")
LEGACY_MATERIALS_FOLDER = os.getenv("SUPABASE_MATERIALS_FOLDER", "pdfs")
MATERIALS_CATEGORY_FOLDERS = {
    "slides": "slides",
    "material-complementar": "pdfs",
    "leituras-recomendadas": "leitura",
}
MATERIALS_ALLOWED_EXTENSIONS = {
    "slides": {".pdf", ".ppt", ".pptx"},
    "material-complementar": {".pdf"},
    "leituras-recomendadas": {".pdf"},
}
MATERIALS_CATEGORIES = set(MATERIALS_CATEGORY_FOLDERS.keys())
MODULE_PATTERN = re.compile(r"modulo[\s_-]*(\d+)", re.IGNORECASE)

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


def _join_storage_path(*parts):
    normalized_parts = []
    for part in parts:
        value = str(part or "").replace("\\", "/").strip("/")
        if value:
            normalized_parts.append(value)
    return "/".join(normalized_parts)


def _normalize_storage_path(path):
    return "/".join(
        segment
        for segment in str(path or "").replace("\\", "/").split("/")
        if segment not in {"", "."}
    )


def _material_title_from_name(file_name):
    title = Path(file_name).stem.replace("_", " ").strip()
    if title.lower().endswith(".docx"):
        title = title[:-5].strip()
    if title.lower().endswith(".pptx"):
        title = title[:-5].strip()
    return title


def _material_module_from_path(storage_path):
    for segment in _normalize_storage_path(storage_path).split("/"):
        match = MODULE_PATTERN.search(segment.lower())
        if match:
            return f"Modulo {int(match.group(1))}"
    return "Sem modulo"


def _material_file_type_from_path(storage_path):
    extension = Path(storage_path).suffix.lower().replace(".", "")
    return extension.upper() if extension else "ARQUIVO"


def _allowed_extensions_for_category(category):
    return MATERIALS_ALLOWED_EXTENSIONS.get(category, {".pdf"})


def _media_type_for_storage_path(storage_path):
    extension = Path(storage_path).suffix.lower()
    if extension == ".pdf":
        return "application/pdf"
    if extension == ".ppt":
        return "application/vnd.ms-powerpoint"
    if extension == ".pptx":
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    guessed_type, _ = mimetypes.guess_type(storage_path)
    return guessed_type or "application/octet-stream"


def _material_sort_key(item):
    module = str(item.get("module", "")).lower()
    match = MODULE_PATTERN.search(module)
    module_number = int(match.group(1)) if match else 999
    return (module_number, module, item["title"].lower())


def _category_storage_roots(category):
    category_folder = MATERIALS_CATEGORY_FOLDERS[category]
    roots = []

    if MATERIALS_ROOT_FOLDER:
        roots.append(_join_storage_path(
            MATERIALS_ROOT_FOLDER, category_folder))

    roots.append(_normalize_storage_path(category_folder))

    if category == "material-complementar" and LEGACY_MATERIALS_FOLDER:
        roots.append(_normalize_storage_path(LEGACY_MATERIALS_FOLDER))

    deduped = []
    seen = set()
    for root in roots:
        if not root or root in seen:
            continue
        deduped.append(root)
        seen.add(root)

    return deduped


def _is_allowed_storage_path(storage_path):
    normalized_path = _normalize_storage_path(storage_path).lower()
    extension = Path(normalized_path).suffix.lower()
    if not extension:
        return False

    if ".." in normalized_path.split("/"):
        return False

    for category in MATERIALS_CATEGORIES:
        for root in _category_storage_roots(category):
            normalized_root = _normalize_storage_path(root).lower()
            if (
                normalized_path == normalized_root
                or normalized_path.startswith(f"{normalized_root}/")
            ):
                return extension in _allowed_extensions_for_category(category)

    return False


def _list_storage_document_paths(category):
    allowed_extensions = _allowed_extensions_for_category(category)

    def _list_folder(path):
        try:
            raw_items = rag_engine.supabase.storage.from_(MATERIALS_BUCKET).list(
                path,
                {
                    "limit": 300,
                    "offset": 0,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
        except Exception:
            return []

        if isinstance(raw_items, dict) and isinstance(raw_items.get("data"), list):
            return raw_items["data"]

        return raw_items or []

    for root in _category_storage_roots(category):
        queue = [root]
        visited = set()
        document_paths = []

        while queue:
            current_folder = _normalize_storage_path(queue.pop(0))
            if not current_folder or current_folder in visited:
                continue

            visited.add(current_folder)

            for item in _list_folder(current_folder):
                name = str(item.get("name", "")).strip()
                if not name:
                    continue

                full_path = _join_storage_path(current_folder, name)
                extension = Path(name).suffix.lower()
                if extension in allowed_extensions:
                    document_paths.append(full_path)
                    continue

                metadata = item.get("metadata")
                if metadata is None or "." not in name:
                    queue.append(full_path)

        if document_paths:
            return sorted(set(document_paths), key=lambda value: value.lower())

    return []


def _build_material_items(category):
    items = []

    for storage_path in _list_storage_document_paths(category):
        file_name = Path(storage_path).name
        title = _material_title_from_name(file_name)

        items.append(
            {
                "id": _slugify(storage_path),
                "title": title,
                "status": "Disponivel",
                "available": True,
                "file_name": file_name,
                "file_path": storage_path,
                "file_type": _material_file_type_from_path(storage_path),
                "module": _material_module_from_path(storage_path),
            }
        )

    items.sort(key=_material_sort_key)

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
    storage_path_param = str(request.query_params.get("path", "")).strip()
    legacy_file_name = Path(
        str(request.query_params.get("file", "")).strip()).name

    if storage_path_param:
        storage_path = _normalize_storage_path(storage_path_param)
    elif legacy_file_name and Path(legacy_file_name).suffix.lower() in {".pdf", ".ppt", ".pptx"}:
        storage_path = _join_storage_path(
            LEGACY_MATERIALS_FOLDER, legacy_file_name)
    else:
        return JSONResponse({"error": "Arquivo invalido."}, status_code=400)

    if not _is_allowed_storage_path(storage_path):
        return JSONResponse({"error": "Caminho de arquivo invalido."}, status_code=400)

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
        media_type=_media_type_for_storage_path(storage_path),
        headers={
            "Content-Disposition": f'attachment; filename="{Path(storage_path).name}"'},
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
