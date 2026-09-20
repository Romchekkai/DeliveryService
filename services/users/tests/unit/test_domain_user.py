from uuid import uuid4

import pytest
from user_service.domain.entities.user import User
from user_service.domain.exceptions import InvalidRoleTransitionError
from user_service.domain.value_objects.email import Email
from user_service.domain.value_objects.password_hash import PasswordHash
from user_service.domain.value_objects.role import Role
from user_service.domain.value_objects.status import Status


def make_user(status: Status = Status.ACTIVE, role: Role = Role.USER) -> User:
    return User(
        id=uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hash"),
        role=role,
        status=status,
    )


class TestEmailValueObject:
    @pytest.mark.parametrize(
        "value",
        ["user@example.com", "first.last@example.co.uk", "user+tag@sub.example.org", "a1@b2.io"],
    )
    def test_valid_email(self, value: str) -> None:
        assert str(Email(value)) == value

    def test_empty_email_raises(self) -> None:
        with pytest.raises(ValueError):
            Email("")

    @pytest.mark.parametrize(
        "value",
        [
            "no-at-sign",
            "@no-local.com",
            "user@",
            "user@domain",
            "user@@domain.com",
            "user name@domain.com",
            "a..b@domain.com",
        ],
    )
    def test_invalid_email_raises(self, value: str) -> None:
        with pytest.raises(ValueError):
            Email(value)

    def test_emails_are_compared_by_value(self) -> None:
        assert Email("a@b.com") == Email("a@b.com")
        assert Email("a@b.com") != Email("c@b.com")


class TestPasswordHashValueObject:
    def test_empty_hash_raises(self) -> None:
        with pytest.raises(ValueError):
            PasswordHash("")


class TestUserRegister:
    def test_register_creates_active_user_with_user_role(self) -> None:
        user = User.register(Email("new@example.com"), PasswordHash("h"))

        assert user.role is Role.USER
        assert user.status is Status.ACTIVE
        assert user.is_active()

    def test_register_generates_unique_ids(self) -> None:
        a = User.register(Email("a@example.com"), PasswordHash("h"))
        b = User.register(Email("b@example.com"), PasswordHash("h"))

        assert a.id != b.id


class TestUserBlockActivate:
    def test_block_sets_status_blocked(self) -> None:
        user = make_user()
        user.block()

        assert user.status is Status.BLOCKED
        assert not user.is_active()

    def test_activate_sets_status_active(self) -> None:
        user = make_user(status=Status.BLOCKED)
        user.activate()

        assert user.status is Status.ACTIVE
        assert user.is_active()


class TestUserChangeRole:
    def test_change_role_when_active(self) -> None:
        user = make_user()
        user.change_role(Role.ADMIN)

        assert user.role is Role.ADMIN

    def test_change_role_when_blocked_raises(self) -> None:
        user = make_user(status=Status.BLOCKED)

        with pytest.raises(InvalidRoleTransitionError):
            user.change_role(Role.ADMIN)
        assert user.role is Role.USER
