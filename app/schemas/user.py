from pydantic import BaseModel, EmailStr
# --- Request body for /signup ---
# This is what the user sends when registering
# Pydantic will automatically validate that:
#   - email is a valid email format
#   - password is a string

class UserCreate(BaseModel):
    email: EmailStr
    password: str

#request for login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

#response after succesful llogin
class TokenResponse(BaseModel):
    access_token: str #the jwt token 
    token_type: str # always "bearer"