import os # To read environment variables
import bcrypt
from datetime import datetime, timedelta #to set token expiration
from jose import jwt 
from dotenv import load_dotenv # to load environment variables from .env file

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# --- Password Hashing Setup ---
# CryptContext handles all bcrypt hashing for us
# "bcrypt" is the algorithm — it's the industry standard for password storage
# deprecated="auto" means older hashing schemes get auto-upgraded

def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8") # converts plain text to hashed passwds using bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8")) #compares plain text to hashed password

def create_access_token(data: dict) -> str:#creates a jwt token, signed with secret key
    to_encode = data.copy() #to not change the original dict

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire}) 

    encoded_jwt = jwt.encode(to_encode, str(SECRET_KEY), algorithm=str(ALGORITHM)) #encode the jwt with the secret key and algorithm
    return encoded_jwt

