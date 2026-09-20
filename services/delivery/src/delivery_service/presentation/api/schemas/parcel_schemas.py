from uuid import UUID

from pydantic import BaseModel, Field


class ParcelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    weight_kg: float = Field(gt=0, lt=500)
    parcel_type_id: int
    content_cost_cents: int = Field(ge=0, description="Content cost in cents")


class ParcelCreateResponse(BaseModel):
    id: UUID
    name: str
    parcel_type: str
    delivery_cost_rub: str


class ParcelResponse(BaseModel):
    id: UUID
    name: str
    weight_kg: float
    parcel_type: str
    content_cost_usd: float
    delivery_cost_rub: str
    status: str


class ParcelShortResponse(BaseModel):
    name: str
    parcel_type: str
    delivery_cost_rub: str


class ParcelTypeResponse(BaseModel):
    id: int
    name: str


class TaskRunResponse(BaseModel):
    task: str
    processed: int
    detail: str
