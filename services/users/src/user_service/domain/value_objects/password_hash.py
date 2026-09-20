from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordHash:
    """To store the password hash"""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Password cannot be empty")
