from dataclasses import dataclass


@dataclass(frozen=True)
class TokenPairOutputDTO:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class RefreshTokenInputDTO:
    refresh_token: str
