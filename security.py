from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MAX_BCRYPT_LEN = 72

def hash_password(password: str) -> str:
    truncated = password[:MAX_BCRYPT_LEN]
    return pwd_context.hash(truncated)

def verify_password(password: str, hashed: str) -> bool:
    truncated = password[:MAX_BCRYPT_LEN]
    return pwd_context.verify(truncated, hashed)
