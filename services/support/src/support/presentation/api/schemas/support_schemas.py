from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500, examples=["Можно ли отправить ноутбук?"])


class SourceResponse(BaseModel):
    section: str
    text: str
    score: float


class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
