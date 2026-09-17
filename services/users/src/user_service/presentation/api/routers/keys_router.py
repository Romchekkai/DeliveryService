from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from user_service.infrastructure.di import token_service
from user_service.infrastructure.security.jwks_converter import pem_to_jwk

router = APIRouter(tags=["keys"])


@router.get("/.well-known/jwks.json", summary="JWKS — публичные ключи для проверки JWT")
async def jwks() -> dict[str, list[dict[str, str]]]:
    versions = token_service.get_all_key_versions()
    keys = [pem_to_jwk(token_service.get_public_key_pem(version=v), kid=str(v)) for v in versions]
    return {"keys": keys}


@router.get(
    "/keys/public",
    response_class=PlainTextResponse,
    summary="Публичный ключ в формате PEM (текущая версия)",
)
async def public_key_pem() -> str:
    return token_service.get_public_key_pem()
