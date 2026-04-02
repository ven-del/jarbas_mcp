import pathlib
import os
import re
import fitz
from supabase import create_client
from storage3.exceptions import StorageApiError
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Defina SUPABASE_URL e SUPABASE_KEY (ou SUPABASE_SERVICE_ROLE_KEY) no .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
MATERIALS_BUCKET = os.environ.get("SUPABASE_MATERIALS_BUCKET", "course-docs")
STORAGE_ROOT = os.environ.get("SUPABASE_MATERIALS_ROOT", "docs")
embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")
TARGET_EMBEDDING_DIM = int(os.environ.get("TARGET_EMBEDDING_DIM", "1536"))
MODULE_PATTERN = re.compile(r"modulo[\s_-]*(\d+)", re.IGNORECASE)
UPLOAD_EXTENSIONS = {".pdf", ".ppt", ".pptx"}

DOCS_DIR = pathlib.Path(__file__).parent / "docs"


_dim_warning_printed = False


def normalize_embedding_dimension(vector, target_dim):
    global _dim_warning_printed

    current_dim = len(vector)
    if current_dim == target_dim:
        return vector

    if not _dim_warning_printed:
        print(
            f"Aviso: embedding gerado com {current_dim} dimensoes; ajustando para {target_dim} para compatibilidade com o banco."
        )
        _dim_warning_printed = True

    if current_dim > target_dim:
        return vector[:target_dim]
    return vector + [0.0] * (target_dim - current_dim)


def embed(text):
    vector = embeddings_model.embed_query(text)
    return normalize_embedding_dimension(vector, TARGET_EMBEDDING_DIM)


def build_storage_path(local_path):
    relative_path = local_path.relative_to(DOCS_DIR).as_posix()
    root = STORAGE_ROOT.strip("/")
    if not root:
        return relative_path
    return f"{root}/{relative_path}"


def infer_module(local_path):
    relative_parts = [part.lower()
                      for part in local_path.relative_to(DOCS_DIR).parts]
    for part in relative_parts:
        match = MODULE_PATTERN.search(part)
        if match:
            return f"modulo_{int(match.group(1))}"

    if relative_parts:
        return relative_parts[0].replace("-", "_")

    return "material_apoio"


def upload_file(local_path):
    storage_path = build_storage_path(local_path)
    try:
        with open(local_path, "rb") as f:
            supabase.storage.from_(MATERIALS_BUCKET).upload(
                storage_path, f, {"upsert": "true"}
            )
        public_url = supabase.storage.from_(MATERIALS_BUCKET).get_public_url(
            storage_path)
        if isinstance(public_url, dict):
            return public_url.get("publicUrl") or public_url.get("publicURL")
        return public_url
    except StorageApiError as exc:
        print(
            "Aviso: nao foi possivel enviar arquivo ao Supabase Storage. "
            f"Verifique policy do bucket '{MATERIALS_BUCKET}' ou use SUPABASE_SERVICE_ROLE_KEY. "
            f"Detalhe: {exc}"
        )
        return None


def ingest_pdf(path):
    print(f"Processando: {path.name}")
    url = upload_file(path)

    if url:
        # Evita duplicacao quando o mesmo PDF eh reprocessado.
        supabase.table("documents").delete().eq("storage_url", url).execute()

    doc = fitz.open(str(path))
    text = "\n".join(page.get_text() for page in doc)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)

    for chunk in chunks:
        row = {
            "title": path.stem,
            "content": chunk,
            "doc_type": "pdf",
            "storage_url": url or "",
            "module": infer_module(path),
            "embedding": embed(chunk)
        }
        supabase.table("documents").insert(row).execute()

    print(f"  -> {len(chunks)} chunks salvos")


def upload_non_pdf(path):
    print(f"Processando: {path.name}")
    url = upload_file(path)

    if url:
        print("  -> upload concluido (sem ingestao vetorial para esta extensao)")
    else:
        print("  -> falha no upload")


if __name__ == "__main__":
    for material in sorted(DOCS_DIR.rglob("*")):
        if not material.is_file() or material.suffix.lower() not in UPLOAD_EXTENSIONS:
            continue

        if material.suffix.lower() == ".pdf":
            ingest_pdf(material)
            continue

        upload_non_pdf(material)
