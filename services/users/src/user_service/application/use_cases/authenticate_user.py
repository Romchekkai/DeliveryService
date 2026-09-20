from user_service.application.dto.token_dto import TokenPairOutputDTO
from user_service.application.dto.user_dto import LoginInputDTO
from user_service.application.interfaces.password_hasher import PasswordHasher
from user_service.application.interfaces.refresh_token_hasher import RefreshTokenHasher
from user_service.application.interfaces.token_service import TokenService
from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.exceptions import InvalidCredentialsError
from user_service.domain.repositories import IUserRepository, RefreshTokenRepository
from user_service.domain.value_objects.email import Email


class AuthenticateUserUseCase:
    def __init__(
        self,
        user_repository: IUserRepository,
        refresh_token_repository: RefreshTokenRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        refresh_token_hasher: RefreshTokenHasher,
    ):
        self._repo = user_repository
        self._refresh_repo = refresh_token_repository
        self._hasher = password_hasher
        self._tokens = token_service
        self._refresh_hasher = refresh_token_hasher

    async def execute(self, input_dto: LoginInputDTO) -> TokenPairOutputDTO:
        email = Email(input_dto.email)
        user = await self._repo.get_by_email(email)

        if user is None or not self._hasher.verify_password(
            input_dto.password, user.password_hash.value
        ):
            raise InvalidCredentialsError("Email or password incorrect.")

        if not user.is_active():
            raise InvalidCredentialsError("User is not active")

        access_token = self._tokens.generate_access_token(user_id=user.id, role=user.role)

        raw_refresh = self._refresh_hasher.generate_raw_token()
        refresh_entity = RefreshToken.create(
            user_id=user.id,
            token_hash=self._refresh_hasher.hash(raw_refresh),
        )
        await self._refresh_repo.add(refresh_entity)

        return TokenPairOutputDTO(access_token=access_token, refresh_token=raw_refresh)
