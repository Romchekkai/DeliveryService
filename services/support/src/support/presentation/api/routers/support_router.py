import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from support.config import rag_settings
from support.di import get_vector_store, llm_client
from support.presentation.api.schemas.support_schemas import (
    AnswerResponse,
    QuestionRequest,
    SourceResponse,
)
from support.rag.answer_question import AnswerQuestionUseCase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


def get_answer_use_case() -> AnswerQuestionUseCase:
    return AnswerQuestionUseCase(
        vector_store=get_vector_store(),
        llm_client=llm_client,
        top_k=rag_settings.top_k,
    )


@router.post(
    "/ask",
    response_model=AnswerResponse,
    summary="Задать вопрос службе поддержки",
)
async def ask(
    request: QuestionRequest,
    use_case: AnswerQuestionUseCase = Depends(get_answer_use_case),
) -> AnswerResponse:
    try:
        result = await use_case.execute(request.question)
    except Exception as e:
        logger.error("rag_failed", question=request.question, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис поддержки временно недоступен",
        ) from e

    return AnswerResponse(
        answer=result.answer,
        sources=[
            SourceResponse(section=s.section, text=s.text, score=s.score) for s in result.sources
        ],
    )
