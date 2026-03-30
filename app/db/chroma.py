import logging
from pathlib import Path

import chromadb


logger = logging.getLogger("documind.chroma")


class ChromaVectorStore:
    """Persists embeddings and text chunks in a local Chroma collection."""

    def __init__(
        self,
        persist_directory: Path,
        collection_name: str = "documind_chunks",
    ):
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Connected to Chroma collection: %s", collection_name)

    def add_chunks(
        self,
        document_id: str,
        filename: str,
        chunks: list[dict],
        embeddings: list[list[float]],
        stored_name: str | None = None,
    ) -> None:
        ids = [f"{document_id}-{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "stored_name": stored_name or "",
                "chunk_index": index,
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "page_numbers": ",".join(str(page) for page in chunk["page_numbers"]),
                "page_label": self._build_page_label(chunk["page_start"], chunk["page_end"]),
            }
            for index, chunk in enumerate(chunks)
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=[chunk["text"] for chunk in chunks],
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: list[float],
        limit: int = 3,
        document_id: str | None = None,
    ) -> list[dict]:
        query_args = {
            "query_embeddings": [embedding],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if document_id:
            query_args["where"] = {"document_id": document_id}

        results = self.collection.query(**query_args)
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "text": document,
                "document_id": metadata["document_id"],
                "filename": metadata["filename"],
                "stored_name": metadata.get("stored_name", ""),
                "chunk_index": metadata["chunk_index"],
                "page_start": metadata.get("page_start", 1),
                "page_end": metadata.get("page_end", metadata.get("page_start", 1)),
                "page_numbers": self._parse_page_numbers(metadata.get("page_numbers", "")),
                "page_label": metadata.get(
                    "page_label",
                    self._build_page_label(
                        metadata.get("page_start", 1),
                        metadata.get("page_end", metadata.get("page_start", 1)),
                    ),
                ),
                "distance": distance,
            }
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]

    def list_documents(self) -> list[dict]:
        results = self.collection.get(include=["metadatas"])
        metadatas = results.get("metadatas", [])

        documents: dict[str, dict] = {}
        for metadata in metadatas:
            document_id = metadata["document_id"]
            document = documents.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "filename": metadata["filename"],
                    "stored_name": metadata.get("stored_name", ""),
                    "chunk_count": 0,
                    "page_start": metadata.get("page_start", 1),
                    "page_end": metadata.get("page_end", metadata.get("page_start", 1)),
                },
            )
            document["chunk_count"] += 1
            document["page_start"] = min(document["page_start"], metadata.get("page_start", 1))
            document["page_end"] = max(
                document["page_end"],
                metadata.get("page_end", metadata.get("page_start", 1)),
            )

        listed_documents = []
        for document in documents.values():
            listed_documents.append(
                {
                    **document,
                    "page_label": self._build_page_label(document["page_start"], document["page_end"]),
                }
            )

        return sorted(listed_documents, key=lambda item: item["filename"].lower())

    def delete_document(self, document_id: str) -> dict | None:
        results = self.collection.get(where={"document_id": document_id}, include=["metadatas"])
        metadatas = results.get("metadatas", [])
        ids = results.get("ids", [])

        if not metadatas or not ids:
            return None

        first_metadata = metadatas[0]
        self.collection.delete(ids=ids)
        return {
            "document_id": document_id,
            "filename": first_metadata["filename"],
            "stored_name": first_metadata.get("stored_name", ""),
            "deleted_chunks": len(ids),
        }

    @staticmethod
    def _build_page_label(page_start: int, page_end: int) -> str:
        if page_start == page_end:
            return f"Page {page_start}"
        return f"Pages {page_start}-{page_end}"

    @staticmethod
    def _parse_page_numbers(page_numbers: str) -> list[int]:
        if not page_numbers:
            return []
        return [int(page) for page in page_numbers.split(",") if page]
