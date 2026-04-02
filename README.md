# Jarbas

O amado assistente de IA Generativa com interface web, RAG com Supabase e integração com Gemini.

## Visao geral

O Jarbas é um assistente para apoiar estudos em IA Generativa. O projeto possui:
- Chat web para perguntas e respostas com contexto da base vetorial.
- Listagem e download de materiais (slides, material complementar e leituras).
- Pipeline de ingestao para upload de arquivos e indexacao vetorial de PDFs.

## Tecnologias utilizadas

- Python 3.11
- FastHTML (ASGI) + Starlette
- Google Gemini (google-genai)
- Supabase (Postgres + Storage)
- LangChain (text splitter + embeddings)
- sentence-transformers (all-MiniLM-L6-v2)
- PyMuPDF (leitura de PDF)
- Frontend: HTML, CSS e JavaScript vanilla
- Docker e Docker Compose

## Estrutura principal

- `jarbas.py`: servidor web e endpoints HTTP.
- `rag_utils.py`: mecanismo de busca de contexto (RAG).
- `ingest.py`: upload para Storage e ingestao vetorial de PDFs.
- `persona.md`: instrucoes de persona do assistente.
- `assets/`: frontend estatico (paginas, estilos e scripts).

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com os valores necessarios:

```env
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...

# Opcional para ingestao com mais permissao
SUPABASE_SERVICE_ROLE_KEY=...

# Opcional
GEMINI_MODEL=gemini-2.5-flash
TARGET_EMBEDDING_DIM=1536
SUPABASE_MATERIALS_BUCKET=course-docs
SUPABASE_MATERIALS_ROOT=docs
SUPABASE_MATERIALS_FOLDER=pdfs
```

## Como rodar localmente (sem Docker)

1. Criar e ativar ambiente virtual:

```bash
python -m venv venv
source venv/Scripts/activate
```

2. Instalar dependências:

```bash
pip install -r requirements.txt
```

3. Iniciar o servidor:

```bash
python jarbas.py
```

4. Abrir no navegador:

- http://localhost:5001

## Como rodar com Docker Compose

1. Garanta que o arquivo `.env` existe na raiz.
2. Suba a aplicação:

```bash
docker compose up --build
```

3. Acesse:

- http://localhost:5001

### Executar ingestão via Compose (opcional)

A ingestão foi separada em um serviço com profile para execução sob demanda.

```bash
docker compose --profile ingest run --rm ingest
```

## Observacoes importantes

- O servico web depende de credenciais validas do Supabase e da API Gemini.
- A ingestao vetorial ocorre apenas para arquivos PDF; PPT/PPTX sao enviados para Storage sem vetorizacao.
- Para ingestao em ambientes com RLS, prefira `SUPABASE_SERVICE_ROLE_KEY`.
