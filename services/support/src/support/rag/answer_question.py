from dataclasses import dataclass

import structlog

from support.rag.llm_client import LLMClient
from support.rag.vector_store import InMemoryVectorStore

logger = structlog.get_logger(__name__)

MIN_RELEVANCE_SCORE = 0.25


@dataclass(frozen=True)
class SourceDTO:
    section: str
    text: str
    score: float


@dataclass(frozen=True)
class AnswerDTO:
    answer: str
    sources: list[SourceDTO]


class AnswerQuestionUseCase:
    """Векторизуем вопрос → ищем контекст → отдаём в LLM."""

    def __init__(self, vector_store: InMemoryVectorStore, llm_client: LLMClient, top_k: int = 4):
        self._store = vector_store
        self._llm = llm_client
        self._top_k = top_k

    async def execute(self, question: str) -> AnswerDTO:
        found = self._store.search(question, top_k=self._top_k)
        relevant = [(c, s) for c, s in found if s >= MIN_RELEVANCE_SCORE]

        if not relevant:
            logger.info("rag_no_relevant_context", question=question)
            return AnswerDTO(
                answer=(
                    "Не нашёл ответа в базе знаний. "
                    "Пожалуйста, уточните вопрос или обратитесь к оператору."
                ),
                sources=[],
            )

        context = "\n\n".join(f"[{chunk.section}] {chunk.text}" for chunk, _ in relevant)
        answer = await self._llm.generate(question, context)

        logger.info(
            "rag_answered",
            question=question,
            sources_count=len(relevant),
            top_score=round(relevant[0][1], 3),
        )

        return AnswerDTO(
            answer=answer,
            sources=[
                SourceDTO(section=chunk.section, text=chunk.text, score=round(score, 3))
                for chunk, score in relevant
            ],
        )
