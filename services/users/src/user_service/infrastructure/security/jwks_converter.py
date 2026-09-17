import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey


def pem_to_jwk(public_key_pem: str, kid: str) -> dict[str, str]:
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    if not isinstance(public_key, RSAPublicKey):
        raise TypeError("Ожидался RSA-ключ")
    numbers = public_key.public_numbers()

    def to_base64url(value: int) -> str:
        byte_length = (value.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(value.to_bytes(byte_length, "big")).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": to_base64url(numbers.n),
        "e": to_base64url(numbers.e),
    }
