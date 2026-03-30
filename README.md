# DocuMind Lite

DocuMind Lite is a minimal document intelligence app for uploading PDFs and asking grounded questions about their contents. It uses FastAPI on the backend, a vanilla HTML/CSS/JavaScript frontend, sentence-transformers for embeddings, ChromaDB for vector search, LangChain for model orchestration, and LangGraph for the agent workflow.

## Features

- Upload one or more PDFs with `POST /upload`
- Drag-and-drop upload zone for faster document ingestion
- Delete indexed PDFs with `DELETE /documents/{document_id}`
- Extract text with `pypdf`
- Chunk text into 500-word chunks with 50-word overlap
- Track source pages for every chunk
- Generate embeddings with `sentence-transformers`
- Store chunks and embeddings in ChromaDB
- Ask questions with `POST /ask`
- Search a single document or all indexed documents
- Retrieve the top 3 to 5 relevant chunks and answer with inline source citations such as `[Source 1]`
- Display source confidence labels on retrieved chunks
- Copy generated answers with one click
- Keep a recent-question history in the browser for prompt reuse
- List indexed documents with `GET /documents`
- Show an explainable LangGraph workflow with visible planning, retrieval, refinement, and generation steps
- Basic logging, loading state, keyboard shortcut support, and input validation

## Agentic Layer

DocuMind Lite now uses a real LangGraph planner-executor workflow on top of the RAG pipeline.

The graph runs these steps:

- `plan`: build a question plan using LangChain structured output when OpenAI is available, with a heuristic fallback when it is not
- `retrieve_primary`: run the first similarity search against ChromaDB
- `retrieve_refined`: conditionally run a second retrieval pass when evidence is weak or incomplete
- `generate_answer`: produce the final grounded answer with inline citations

This makes the app more than a fixed retrieve-and-answer flow: it now performs explicit graph-based planning and adaptive execution before answer generation.

## LangChain Usage

- `ChatOpenAI` is used through `langchain-openai` when `OPENAI_API_KEY` is available
- `HuggingFacePipeline` is used through `langchain-huggingface` as the fallback answer model
- LangChain prompt templates are used to keep planning and answer generation prompts structured

## Project Structure

```text
app/
  main.py
  routes/
  services/
    agent_service.py
    document_service.py
    llm_service.py
  embedding.py
  rag.py
  db/
    chroma.py
frontend/
  index.html
  style.css
  script.js
requirements.txt
Dockerfile
docker-compose.yml
.github/workflows/deploy.yml
README.md
```

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Optional OpenAI API key | unset |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `HUGGINGFACE_MODEL` | Hugging Face fallback model | `google/flan-t5-base` |
| `EMBEDDING_MODEL` | Sentence-transformers embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| `UPLOAD_DIR` | Local directory for uploaded PDFs | `./uploads` |
| `CHROMA_PERSIST_DIR` | Local Chroma persistence directory | `./chroma_data` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## Local Run

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the application:

```bash
python -m uvicorn app.main:app --reload
```

4. Open `http://localhost:8000`

The first run may take a little longer because the embedding model and Hugging Face fallback model are downloaded locally.

## Docker Run

```bash
docker-compose up --build
```

Open `http://localhost:8000` after the container starts.

## Frontend Highlights

- Drag a PDF into the upload zone or click to browse
- Use `Ctrl + Enter` in the question box to submit quickly
- Copy the generated answer with one click
- Reuse recent questions from browser-stored history
- Delete documents directly from the indexed library panel
- View the agent workflow steps for each answer
- Open long source chunks in a modal instead of stretching the page

## API Endpoints

### `POST /upload`

- Accepts `multipart/form-data` with a `file` field
- Saves the uploaded PDF to `uploads/`
- Extracts text, preserves page references, and indexes chunks into ChromaDB

### `GET /documents`

Returns the indexed documents currently available in ChromaDB.

### `DELETE /documents/{document_id}`

Deletes an indexed document from ChromaDB and removes its uploaded file when available.

### `POST /ask`

Request body:

```json
{
  "question": "What is the contract duration?",
  "document_id": "optional-document-id"
}
```

If `document_id` is omitted or `null`, the query searches across all indexed documents.

Successful response includes the agent metadata:

```json
{
  "answer": "The contract lasts for 12 months [Source 1].",
  "provider": "OpenAI (gpt-4o-mini)",
  "documents_used": ["example.pdf"],
  "sources": [],
  "agent": {
    "enabled": true,
    "intent": "fact_lookup",
    "strategy": "targeted retrieval",
    "planner_mode": "langchain_structured",
    "steps": [
      {
        "step": "Plan intent",
        "detail": "Detected 'fact_lookup' intent and selected the 'targeted retrieval' strategy using the langchain structured planner."
      },
      {
        "step": "Retrieve evidence",
        "detail": "Ran the primary retrieval pass with the query: What is the contract duration?"
      },
      {
        "step": "Generate answer",
        "detail": "Produced a grounded answer from the merged evidence with inline source citations."
      }
    ]
  }
}
```

## Error Handling

- Empty upload
- Invalid file type
- Invalid or unreadable PDF
- Empty question
- No indexed content found
- Delete requests for missing documents

## CI/CD

The GitHub Actions workflow installs dependencies, runs a basic Python compile check, and builds the Docker image on pushes and pull requests targeting `main`.

## Notes

- The application is designed to stay simple and modular.
- Chroma data and uploads are stored outside the app code directory for easier container mounting.
- Question history is stored in the browser and is not shared across devices.
- For production, place the service behind a reverse proxy and use managed persistent storage.

