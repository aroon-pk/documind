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
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        ids = [f"{document_id}-{index}" for index in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "filename": filename,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
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
                "chunk_index": metadata["chunk_index"],
                "distance": distance,
            }
            for document, metadata, distance in zip(documents, metadatas, distances)
        ]
