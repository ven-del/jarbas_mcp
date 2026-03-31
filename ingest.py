import pathlib
import os
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
embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2")
TARGET_EMBEDDING_DIM = int(os.environ.get("TARGET_EMBEDDING_DIM", "1536"))

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


def upload_file(local_path):
    safe_name = local_path.name.replace(" ", "_").replace("(", "").replace(")", "")
    storage_path = f"pdfs/{safe_name}"
    try:
        with open(local_path, "rb") as f:
            supabase.storage.from_("course-docs").upload(
                storage_path, f, {"upsert": "true"}
            )
        public_url = supabase.storage.from_(
            "course-docs").get_public_url(storage_path)
        if isinstance(public_url, dict):
            return public_url.get("publicUrl") or public_url.get("publicURL")
        return public_url
    except StorageApiError as exc:
        print(
            "Aviso: nao foi possivel enviar PDF ao Supabase Storage. "
            "Verifique policy do bucket 'course-docs' ou use SUPABASE_SERVICE_ROLE_KEY. "
            f"Detalhe: {exc}"
        )
        return None


def ingest_pdf(path):
    print(f"Processando: {path.name}")
    url = upload_file(path)

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
            "module": "material_apoio",
            "embedding": embed(chunk)
        }
        supabase.table("documents").insert(row).execute()

    print(f"  -> {len(chunks)} chunks salvos")


if __name__ == "__main__":
    for pdf in DOCS_DIR.glob("*.pdf"):
        ingest_pdf(pdf)
