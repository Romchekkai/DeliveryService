from abc import ABC, abstractmethod


class RefreshTokenHasher(ABC):
    @abstractmethod
    def hash(self, token: str) -> str: ...

    @abstractmethod
    def generate_raw_token(self) -> str: ...
