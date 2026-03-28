# DocuMind Lite

DocuMind Lite is a minimal RAG web application for uploading PDFs and asking grounded questions about their contents. It uses FastAPI on the backend, a vanilla HTML/CSS/JavaScript frontend, sentence-transformers for embeddings, ChromaDB for vector search, and OpenAI or Hugging Face for answer generation.

## Features

- Upload a PDF with `POST /upload`
- Extract text with `pypdf`
- Chunk text into 500-word chunks with 50-word overlap
- Generate embeddings with `sentence-transformers`
- Store chunks and embeddings in ChromaDB
- Ask questions with `POST /ask`
- Retrieve the top 3 relevant chunks and answer with OpenAI or a Hugging Face fallback model
- Basic logging, loading state, and input validation

## Project Structure

```text
app/
  main.py
  routes/
  services/
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
uvicorn app.main:app --reload
```

4. Open `http://localhost:8000`

The first run may take a little longer because the embedding model and Hugging Face fallback model are downloaded locally.

## Docker Run

```bash
docker-compose up --build
```

Open `http://localhost:8000` after the container starts.

## API Endpoints

### `POST /upload`

- Accepts `multipart/form-data` with a `file` field
- Saves the uploaded PDF to `uploads/`
- Extracts text and indexes chunks into ChromaDB

Successful response:

```json
{
  "message": "PDF uploaded and indexed successfully.",
  "filename": "example.pdf",
  "document_id": "uuid",
  "chunks_indexed": 4
}
```

### `POST /ask`

Request body:

```json
{
  "question": "What is the contract duration?",
  "document_id": "optional-document-id"
}
```

Successful response:

```json
{
  "answer": "The contract lasts for 12 months.",
  "provider": "OpenAI (gpt-4o-mini)",
  "sources": [
    {
      "text": "Relevant chunk text...",
      "document_id": "uuid",
      "filename": "example.pdf",
      "chunk_index": 0,
      "distance": 0.12
    }
  ]
}
```

## Error Handling

- Empty upload
- Invalid file type
- Invalid or unreadable PDF
- Empty question
- No indexed content found

## CI/CD

The GitHub Actions workflow installs dependencies, runs a basic Python compile check, and builds the Docker image on pushes and pull requests targeting `main`.

## Notes

- The application is designed to stay simple and modular.
- Chroma data and uploads are stored outside the app code directory for easier container mounting.
- For production, place the service behind a reverse proxy and use managed persistent storage.
