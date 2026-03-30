import logging
from typing import Any
from uuid import uuid4


logger = logging.getLogger("documind.rag")


def split_pages_into_chunks(
    pages: list[dict],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """Split extracted PDF pages into overlapping chunks while preserving page references."""
    word_entries: list[tuple[str, int]] = []
    for page in pages:
        page_number = int(page["page_number"])
        for word in page["text"].split():
            word_entries.append((word, page_number))

    if not word_entries:
        return []

    step = max(chunk_size - overlap, 1)
    chunks: list[dict[str, Any]] = []

    for start in range(0, len(word_entries), step):
        chunk_entries = word_entries[start : start + chunk_size]
        if not chunk_entries:
            continue

        page_numbers: list[int] = []
        for _, page_number in chunk_entries:
            if page_number not in page_numbers:
                page_numbers.append(page_number)

        chunks.append(
            {
                "text": " ".join(word for word, _ in chunk_entries),
                "page_numbers": page_numbers,
                "page_start": page_numbers[0],
                "page_end": page_numbers[-1],
            }
        )

        if start + chunk_size >= len(word_entries):
            break

    return chunks


def format_page_label(page_start: int, page_end: int) -> str:
    if page_start == page_end:
        return f"Page {page_start}"
    return f"Pages {page_start}-{page_end}"


class RAGService:
    """Coordinates chunking, embedding, retrieval, and answer generation."""

    def __init__(self, embedding_service, vector_store, llm_service):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.llm_service = llm_service

    def index_document(
        self,
        filename: str,
        pages: list[dict],
        stored_name: str | None = None,
    ) -> dict[str, Any]:
        chunks = split_pages_into_chunks(pages)
        if not chunks:
            raise ValueError("The PDF did not contain enough readable text to index.")

        document_id = str(uuid4())
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_service.embed_texts(chunk_texts)
        self.vector_store.add_chunks(
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            embeddings=embeddings,
            stored_name=stored_name,
        )

        logger.info("Indexed %s chunks for %s", len(chunks), filename)
        return {
            "document_id": document_id,
            "chunks_indexed": len(chunks),
            "page_range": format_page_label(chunks[0]["page_start"], chunks[-1]["page_end"]),
        }

    def list_documents(self) -> list[dict[str, Any]]:
        return self.vector_store.list_documents()

    def delete_document(self, document_id: str) -> dict[str, Any] | None:
        return self.vector_store.delete_document(document_id)

    def retrieve_sources(
        self,
        question: str,
        document_id: str | None = None,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("Question cannot be empty.")

        query_embedding = self.embedding_service.embed_query(clean_question)
        retrieved_chunks = self.vector_store.query(
            embedding=query_embedding,
            limit=limit,
            document_id=document_id,
        )

        return self._prepare_sources(retrieved_chunks)

    def answer_with_sources(
        self,
        question: str,
        sources: list[dict[str, Any]],
        answer_instructions: str | None = None,
    ) -> dict[str, Any]:
        if not sources:
            raise LookupError("No relevant content was found. Upload a PDF first.")

        context = self.build_context_from_sources(sources)
        answer = self.llm_service.answer_question(
            question=question.strip(),
            context=context,
            instructions=answer_instructions,
        )

        return {
            "answer": answer,
            "provider": self.llm_service.provider_name,
            "sources": sources,
            "documents_used": sorted({item["filename"] for item in sources}),
        }

    def answer_question(self, question: str, document_id: str | None = None) -> dict[str, Any]:
        sources = self.retrieve_sources(question=question, document_id=document_id, limit=3)
        if not sources:
            raise LookupError("No relevant content was found. Upload a PDF first.")
        return self.answer_with_sources(question=question, sources=sources)

    @staticmethod
    def build_context_from_sources(sources: list[dict[str, Any]]) -> str:
        context_blocks: list[str] = []
        for item in sources:
            context_blocks.append(
                f"[{item['source_label']}] File: {item['filename']} | {item['page_label']}\n{item['text']}"
            )
        return "\n\n".join(context_blocks)

    @staticmethod
    def merge_sources(*source_groups: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        merged: dict[tuple[str, int], dict[str, Any]] = {}

        for group in source_groups:
            for source in group:
                key = (source["document_id"], source["chunk_index"])
                existing = merged.get(key)
                if existing is None or source.get("distance", 1) < existing.get("distance", 1):
                    merged[key] = source

        ranked = sorted(merged.values(), key=lambda item: item.get("distance", 1))[:limit]
        return [
            {
                **source,
                "source_label": f"Source {index}",
            }
            for index, source in enumerate(ranked, start=1)
        ]

    @staticmethod
    def _prepare_sources(retrieved_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        for index, item in enumerate(retrieved_chunks, start=1):
            page_label = item.get("page_label") or format_page_label(
                item["page_start"],
                item["page_end"],
            )
            sources.append(
                {
                    **item,
                    "source_label": f"Source {index}",
                    "page_label": page_label,
                }
            )
        return sources
