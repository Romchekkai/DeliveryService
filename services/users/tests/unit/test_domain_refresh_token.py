from datetime import datetime, timedelta, timezone
from uuid import uuid4

from user_service.domain.entities.refresh_token import RefreshToken


class TestRefreshToken:
    def test_create_is_valid(self) -> None:
        token = RefreshToken.create(user_id=uuid4(), token_hash="h")

        assert token.is_valid()
        assert not token.revoked

    def test_default_ttl_is_14_days(self) -> None:
        token = RefreshToken.create(user_id=uuid4(), token_hash="h")
        delta = token.expires_at - datetime.now(timezone.utc)

        assert timedelta(days=13, hours=23) < delta <= timedelta(days=14)

    def test_custom_ttl(self) -> None:
        token = RefreshToken.create(user_id=uuid4(), token_hash="h", ttl_days=1)
        delta = token.expires_at - datetime.now(timezone.utc)

        assert delta <= timedelta(days=1)

    def test_expired_token_is_invalid(self) -> None:
        token = RefreshToken(
            id=uuid4(),
            user_id=uuid4(),
            token_hash="h",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        assert not token.is_valid()

    def test_revoke_makes_invalid(self) -> None:
        token = RefreshToken.create(user_id=uuid4(), token_hash="h")
        token.revoke()

        assert token.revoked
        assert not token.is_valid()
