import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel


logger = logging.getLogger("documind.routes.ask")
router = APIRouter(tags=["questions"])


class AskRequest(BaseModel):
    question: str
    document_id: str | None = None


@router.post("/ask")
async def ask_question(payload: AskRequest, request: Request):
    rag_service = request.app.state.rag_service

    try:
        return rag_service.answer_question(
            question=payload.question,
            document_id=payload.document_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected query failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to answer the question.",
        ) from exc
