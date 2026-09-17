from user_service.application.dto.user_dto import RegisterUserInputDTO, UserOutputDTO
from user_service.application.interfaces.password_hasher import PasswordHasher
from user_service.domain.entities.user import User
from user_service.domain.exceptions import UserAlreadyExistsError
from user_service.domain.repositories import IUserRepository
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash


class RegisterUser:
    def __init__(self, user_repository: IUserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    async def execute(self, input_user_dto: RegisterUserInputDTO) -> UserOutputDTO:
        email = Email(input_user_dto.email)

        if await self._user_repository.exists_with_email(email):
            raise UserAlreadyExistsError(str(email))

        hashed = self._password_hasher.hash_password(input_user_dto.password)
        user = User.register(email=email, password_hash=PasswordHash(hashed))

        await self._user_repository.add(user)

        return UserOutputDTO(
            id=user.id,
            email=str(user.email),
            role=user.role,
            status=user.status,
        )
