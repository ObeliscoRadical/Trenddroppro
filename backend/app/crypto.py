from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.social_token_encryption_key.encode("utf-8"))


def encrypt_token(raw: str) -> str:
    return _fernet.encrypt(raw.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
