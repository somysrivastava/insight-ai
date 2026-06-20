from turtle import st

from fastapi import APIRouter, Depends, HTTPException, status
from pandas.core.internals.blocks import re
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, TokenResponse

from app.services.auth_service import hash_password, create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Auth"])
# prefix="/auth" means all routes here start with /auth
# tags=["Auth"] groups them nicely in the Swagger docs

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return{
        "message": "User created successfully", "user_id": new_user.id
    }
#whats happening up we are chekcing if a user with existing mail already exists if yes return error if no create a new user and commit it into the datwbase
@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, str(user.hashed_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer"
    }