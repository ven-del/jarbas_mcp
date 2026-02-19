import os
import sys
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings 
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class RAGEngine:
    def __init__(self, pdf_paths):
        
        self.docs = []
        for path in pdf_paths:
            if os.path.exists(path):
                loader = PyPDFLoader(path)
                self.docs.extend(loader.load())
            else:
                print(f"Arquivo não encontrado: {path}", file=sys.stderr)
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

        split = text_splitter.split_documents(self.docs)

        embeddings = HuggingFaceEmbeddings(
            model = "sentence-transformers/all-MiniLM-L6-v2"
        )

        self.vector_store = FAISS.from_documents(
            documents=split, embedding=embeddings
            )
        
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        print("RAG Engine inicializado com sucesso.", file=sys.stderr)

    def buscar_contexto(self, query):
        docs = self.retriever.invoke(query)

        return "\n\n".join([doc.page_content for doc in docs])
