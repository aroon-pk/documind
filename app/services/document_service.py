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
            text = self.extract_text(saved_path)
            if not text.strip():
                raise ValueError("The PDF did not contain readable text.")

            indexed = self.rag_service.index_document(filename=file.filename, text=text)
            return {
                "message": "PDF uploaded and indexed successfully.",
                "filename": file.filename,
                **indexed,
            }
        except Exception:
            if saved_path.exists():
                saved_path.unlink()
            raise

    def extract_text(self, pdf_path: Path) -> str:
        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            raise ValueError("Invalid or unreadable PDF file.") from exc

        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())

        return "\n".join(pages)

    def _build_file_path(self, original_name: str) -> Path:
        safe_name = Path(original_name).name
        return self.upload_dir / f"{uuid4()}_{safe_name}"
