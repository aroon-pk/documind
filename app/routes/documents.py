import logging

from fastapi import APIRouter, HTTPException, Request, status


logger = logging.getLogger("documind.routes.documents")
router = APIRouter(tags=["documents"])


@router.get("/documents")
async def list_documents(request: Request):
    rag_service = request.app.state.rag_service
    return {"documents": rag_service.list_documents()}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request):
    document_service = request.app.state.document_service

    try:
        return document_service.delete_document(document_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected document deletion failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete the document.",
        ) from exc
