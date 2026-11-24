import base64
import hashlib
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

_password_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Gera hash Argon2id seguro para armazenamento de senha."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifica senha em texto puro contra o hash Argon2id armazenado."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def generate_token(nbytes: int = 32) -> str:
    """Gera token aleatório opaco URL-safe para sessão, CSRF ou OAuth state."""
    return secrets.token_urlsafe(nbytes)


def hash_token(raw_token: str) -> str:
    """Armazena apenas o SHA-256 do token de sessão no banco."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _get_fernet() -> Fernet:
    """Retorna instância Fernet a partir de TOKEN_ENCRYPTION_KEY ou chave derivada em dev."""
    settings = get_settings()
    key = settings.token_encryption_key.strip()
    if key and key != "troque_por_uma_chave_fernet_valida":
        try:
            return Fernet(key.encode("utf-8"))
        except Exception:
            pass
    # Fallback determinístico apenas para desenvolvimento local
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(settings.app_secret_key.encode("utf-8")).digest()
    )
    return Fernet(derived)


def encrypt_secret(plain_text: str) -> str:
    """Cifra tokens OAuth ou URLs privadas de feeds ICS antes de persistir."""
    return _get_fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """Decifra segredos armazenados no banco."""
    try:
        return _get_fernet().decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Não foi possível decifrar a credencial armazenada.") from exc
