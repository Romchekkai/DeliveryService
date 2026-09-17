from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from user_service.application.dto.token_dto import RefreshTokenInputDTO
from user_service.application.dto.user_dto import LoginInputDTO, RegisterUserInputDTO, UserOutputDTO
from user_service.application.use_cases.authenticate_user import AuthenticateUserUseCase
from user_service.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from user_service.application.use_cases.register_user import RegisterUser
from user_service.domain.exceptions import DomainError
from user_service.presentation.api.dependencies import (
    get_authenticate_use_case,
    get_current_user,
    get_refresh_use_case,
    get_register_use_case,
)
from user_service.presentation.api.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest, use_case: Annotated[RegisterUser, Depends(get_register_use_case)]
) -> UserResponse:
    try:
        result = await use_case.execute(
            RegisterUserInputDTO(email=request.email, password=request.password)
        )
        return UserResponse(
            id=str(result.id),
            email=result.email,
            role=result.role.value,
            status=result.status.value,
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/login", response_model=TokenPairResponse)
async def login(
    request: LoginRequest,
    use_case: Annotated[AuthenticateUserUseCase, Depends(get_authenticate_use_case)],
) -> TokenPairResponse:
    try:
        result = await use_case.execute(
            LoginInputDTO(email=request.email, password=request.password)
        )
        return TokenPairResponse(
            access_token=result.access_token, refresh_token=result.refresh_token
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    request: RefreshRequest,
    use_case: Annotated[RefreshAccessTokenUseCase, Depends(get_refresh_use_case)],
) -> TokenPairResponse:
    try:
        result = await use_case.execute(RefreshTokenInputDTO(refresh_token=request.refresh_token))
        return TokenPairResponse(
            access_token=result.access_token, refresh_token=result.refresh_token
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Annotated[UserOutputDTO, get_current_user]) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        role=current_user.role.value,
        status=current_user.status.value,
    )
