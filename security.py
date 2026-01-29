from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["sha512_crypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)



def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)
