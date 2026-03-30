import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader


logger = logging.getLogger("documind.document")


class DocumentService:
    """Handles file validation, storage, and PDF text extraction."""

    def __init__(self, upload_dir: Path, rag_service):
        self.upload_dir = upload_dir
        self.rag_service = rag_service

    async def process_upload(self, file: UploadFile) -> dict:
        if not file.filename:
            raise ValueError("Please choose a PDF file to upload.")

        if not file.filename.lower().endswith(".pdf"):
            raise ValueError("Invalid file type. Only PDF files are supported.")

        file_bytes = await file.read()
        if not file_bytes:
            raise ValueError("The uploaded PDF is empty.")

        saved_path = self._build_file_path(file.filename)
        saved_path.write_bytes(file_bytes)
        logger.info("Saved upload to %s", saved_path)

        try:
            pages = self.extract_text(saved_path)
            if not pages:
                raise ValueError("The PDF did not contain readable text.")

            indexed = self.rag_service.index_document(
                filename=file.filename,
                pages=pages,
                stored_name=saved_path.name,
            )
            return {
                "message": "PDF uploaded and indexed successfully.",
                "filename": file.filename,
                "pages_extracted": len(pages),
                **indexed,
            }
        except Exception:
            if saved_path.exists():
                saved_path.unlink()
            raise

    def delete_document(self, document_id: str) -> dict:
        deleted_document = self.rag_service.delete_document(document_id)
        if not deleted_document:
            raise LookupError("Document not found.")

        stored_name = deleted_document.get("stored_name") or ""
        file_deleted = False

        if stored_name:
            stored_path = self.upload_dir / stored_name
            if stored_path.exists():
                stored_path.unlink()
                file_deleted = True
                logger.info("Deleted uploaded file %s", stored_path)

        return {
            "message": "Document deleted successfully.",
            "document_id": deleted_document["document_id"],
            "filename": deleted_document["filename"],
            "deleted_chunks": deleted_document["deleted_chunks"],
            "file_deleted": file_deleted,
        }

    def extract_text(self, pdf_path: Path) -> list[dict]:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            raise ValueError("Invalid or unreadable PDF file.") from exc

        pages: list[dict] = []
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages.append(
                    {
                        "page_number": page_index,
                        "text": page_text,
                    }
                )

        return pages

    def _build_file_path(self, original_name: str) -> Path:
        safe_name = Path(original_name).name
        return self.upload_dir / f"{uuid4()}_{safe_name}"
