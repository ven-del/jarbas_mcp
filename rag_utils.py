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
        self.target_embedding_dim = int(
            os.environ.get("TARGET_EMBEDDING_DIM", "1536"))
        self._dim_warning_printed = False
        print("RAG Engine inicializado com sucesso.", flush=True)

    def _normalize_embedding_dimension(self, vector):
        current_dim = len(vector)
        if current_dim == self.target_embedding_dim:
            return vector

        if not self._dim_warning_printed:
            print(
                f"Aviso: embedding de busca com {current_dim} dimensoes; ajustando para {self.target_embedding_dim} para compatibilidade com o banco.",
                flush=True,
            )
            self._dim_warning_printed = True

        if current_dim > self.target_embedding_dim:
            return vector[:self.target_embedding_dim]
        return vector + [0.0] * (self.target_embedding_dim - current_dim)

    def buscar_contexto(self, query, doc_type=None, k=5):
        embedding = self.embeddings_model.embed_query(query)
        embedding = self._normalize_embedding_dimension(embedding)

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
