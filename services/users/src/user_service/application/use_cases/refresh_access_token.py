from user_service.application.dto.token_dto import RefreshTokenInputDTO, TokenPairOutputDTO
from user_service.application.interfaces.refresh_token_hasher import RefreshTokenHasher
from user_service.application.interfaces.token_service import TokenService
from user_service.domain.entities.refresh_token import RefreshToken
from user_service.domain.exceptions import InvalidTokenError
from user_service.domain.repositories import IUserRepository, RefreshTokenRepository


class RefreshAccessTokenUseCase:
    def __init__(
        self,
        user_repository: IUserRepository,
        refresh_token_repository: RefreshTokenRepository,
        token_service: TokenService,
        refresh_token_hasher: RefreshTokenHasher,
    ):
        self._repo = user_repository
        self._refresh_repo = refresh_token_repository
        self._tokens = token_service
        self._refresh_hasher = refresh_token_hasher

    async def execute(self, input_dto: RefreshTokenInputDTO) -> TokenPairOutputDTO:
        token_hash = self._refresh_hasher.hash(input_dto.refresh_token)
        stored = await self._refresh_repo.get_by_hash(token_hash)

        if stored is None or not stored.is_valid():
            raise InvalidTokenError("Refresh-токен недействителен или истёк")

        stored.revoke()
        await self._refresh_repo.update(stored)

        user = await self._repo.get_by_id(stored.user_id)
        if user is None or not user.is_active():
            raise InvalidTokenError("Пользователь не найден или неактивен")

        access_token = self._tokens.generate_access_token(user_id=user.id, role=user.role)

        raw_refresh = self._refresh_hasher.generate_raw_token()
        new_refresh_entity = RefreshToken.create(
            user_id=user.id,
            token_hash=self._refresh_hasher.hash(raw_refresh),
        )
        await self._refresh_repo.add(new_refresh_entity)

        return TokenPairOutputDTO(access_token=access_token, refresh_token=raw_refresh)
