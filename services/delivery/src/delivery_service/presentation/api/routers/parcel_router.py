from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from delivery_service.application.dto.parcel_dto import ParcelInputDTO
from delivery_service.application.use_cases.get_parcel_by_id import GetParcelsByIdUseCase
from delivery_service.application.use_cases.get_parcel_types import GetParcelTypesUseCase
from delivery_service.application.use_cases.get_parcels_by_user import GetParcelsByUserUseCase
from delivery_service.application.use_cases.parcel_create import CreateParcelUseCase
from delivery_service.domain.exceptions import (
    DomainError,
    ParcelNotFoundError,
    ParcelTypeNotFoundError,
)
from delivery_service.infrastructure.security.jwt_verifier import TokenPayload
from delivery_service.presentation.api.dependencies import (
    get_create_parcel_use_case,
    get_current_user,
    get_parcel_by_id_use_case,
    get_parcel_types_use_case,
    get_parcels_by_user_use_case,
)
from delivery_service.presentation.api.schemas.parcel_schemas import (
    ParcelCreateRequest,
    ParcelCreateResponse,
    ParcelResponse,
    ParcelShortResponse,
    ParcelTypeResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/parcels", tags=["parcels"])


@router.post("", response_model=ParcelCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_parcel(
    request: ParcelCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),
    use_case: CreateParcelUseCase = Depends(get_create_parcel_use_case),
) -> ParcelCreateResponse:
    try:
        result = await use_case.execute(
            ParcelInputDTO(
                user_id=current_user.user_id,
                name=request.name,
                weight=request.weight_kg,
                parcel_type_id=request.parcel_type_id,
                content_cost_cents=request.content_cost_cents,
            )
        )
    except ParcelTypeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    logger.info("parcel_created", parcel_id=str(result.id), user_id=str(current_user.user_id))
    return ParcelCreateResponse(
        id=result.id,
        name=result.name,
        parcel_type=result.parcel_type.name,
        delivery_cost_rub=result.delivery_cost_rub,
    )


@router.get("", response_model=list[ParcelShortResponse])
async def get_my_parcels(
    limit: int = Query(5, ge=1, le=100),
    name_filter: str = Query("", description="Name filter"),
    current_user: TokenPayload = Depends(get_current_user),
    use_case: GetParcelsByUserUseCase = Depends(get_parcels_by_user_use_case),
) -> list[ParcelShortResponse]:
    parcels = await use_case.execute(current_user.user_id, limit, name_filter)
    return [
        ParcelShortResponse(
            name=p.name,
            parcel_type=p.parcel_type,
            delivery_cost_rub=p.delivery_cost_rub,
        )
        for p in parcels
    ]


@router.get("/types", response_model=list[ParcelTypeResponse])
async def get_parcel_types(
    use_case: GetParcelTypesUseCase = Depends(get_parcel_types_use_case),
) -> list[ParcelTypeResponse]:
    types = await use_case.execute()
    return [ParcelTypeResponse(id=t.id, name=t.name) for t in types]


@router.get("/{parcel_id}", response_model=ParcelResponse)
async def get_parcel(
    parcel_id: UUID,
    current_user: TokenPayload = Depends(get_current_user),
    use_case: GetParcelsByIdUseCase = Depends(get_parcel_by_id_use_case),
) -> ParcelResponse:
    try:
        p = await use_case.execute(parcel_id, current_user.user_id)
    except ParcelNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parcel not found")

    return ParcelResponse(
        id=p.id,
        name=p.name,
        weight_kg=p.weight_kg,
        parcel_type=p.parcel_type,
        content_cost_usd=float(p.content_cost_usd),
        delivery_cost_rub=p.delivery_cost_rub,
        status=p.status,
    )
