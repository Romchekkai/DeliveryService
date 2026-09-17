import bcrypt

from user_service.application.interfaces.password_hasher import PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify_password(self, password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
