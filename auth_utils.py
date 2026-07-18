import hashlib
import logging

from passlib.context import CryptContext


logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password for newly created or reset users."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify bcrypt hashes and legacy salt$sha256 hashes."""
    if not hashed_password:
        return False

    if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            logger.exception("Failed to verify bcrypt password hash")
            return False

    try:
        salt, stored_hash = hashed_password.split("$", 1)
        password_hash = hashlib.sha256((plain_password + salt).encode("utf-8")).hexdigest()
        return password_hash == stored_hash
    except Exception:
        return False
