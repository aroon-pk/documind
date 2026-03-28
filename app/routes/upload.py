import logging

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status


logger = logging.getLogger("documind.routes.upload")
router = APIRouter(tags=["documents"])


@router.post("/upload")
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    document_service = request.app.state.document_service

    try:
        result = await document_service.process_upload(file)
        return result
    except ValueError as exc:
        logger.warning("Upload validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected upload failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process the uploaded PDF.",
        ) from exc
