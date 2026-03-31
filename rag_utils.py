import os
from supabase import create_client
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

class RAGEngine:
    def __init__(self):
        self.supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"]
        )
        self.embeddings_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        print("RAG Engine inicializado com sucesso.", flush=True)

    def buscar_contexto(self, query, doc_type=None, k=5):
        embedding = self.embeddings_model.embed_query(query)

        params = {"query_embedding": embedding, "match_count": k}
        if doc_type:
            params["filter_type"] = doc_type

        result = self.supabase.rpc("search_documents", params).execute()

        if not result.data:
            return ""

        partes = []
        for doc in result.data:
            partes.append(
                f"[{doc['doc_type'].upper()}] {doc['title']}\n"
                f"{doc['content']}\n"
                f"Fonte: {doc['storage_url']}"
            )

        return "\n\n---\n\n".join(partes)