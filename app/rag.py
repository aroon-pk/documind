import logging
from typing import Any
from uuid import uuid4


logger = logging.getLogger("documind.rag")


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split extracted text into overlapping word chunks."""
    words = text.split()
    if not words:
        return []

    step = max(chunk_size - overlap, 1)
    chunks: list[str] = []

    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            continue
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break

    return chunks


class RAGService:
    """Coordinates chunking, embedding, retrieval, and answer generation."""

    def __init__(self, embedding_service, vector_store, llm_service):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service

    def index_document(self, filename: str, text: str) -> dict[str, Any]:
        chunks = split_text_into_chunks(text)
        if not chunks:
            raise ValueError("The PDF did not contain enough readable text to index.")

        document_id = str(uuid4())
        embeddings = self.embedding_service.embed_texts(chunks)
        self.vector_store.add_chunks(
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
        )

        logger.info("Indexed %s chunks for %s", len(chunks), filename)
        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks),
        }

    def answer_question(self, question: str, document_id: str | None = None) -> dict[str, Any]:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question cannot be empty.")

        query_embedding = self.embedding_service.embed_query(clean_question)
        retrieved_chunks = self.vector_store.query(
            embedding=query_embedding,
            limit=3,
            document_id=document_id,
        )

        if not retrieved_chunks:
            raise LookupError("No relevant content was found. Upload a PDF first.")

        context = "\n\n".join(
            [
                f"Chunk {index + 1} ({item['filename']}):\n{item['text']}"
                for index, item in enumerate(retrieved_chunks)
            ]
        )

        answer = self.llm_service.answer_question(
            question=clean_question,
            context=context,
        )

        return {
            "answer": answer,
            "provider": self.llm_service.provider_name,
            "sources": retrieved_chunks,
        }
