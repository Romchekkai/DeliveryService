from uuid import UUID

from user_service.application.dto.user_dto import UserOutputDTO
from user_service.domain.exceptions import UserNotFoundError
from user_service.domain.repositories import IUserRepository


class GetUserByIdUseCase:
    def __init__(self, user_repository: IUserRepository):
        self._repo = user_repository

    async def execute(self, user_id: UUID) -> UserOutputDTO:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        return UserOutputDTO(
            id=user.id,
            email=str(user.email),
            role=user.role,
            status=user.status,
        )
