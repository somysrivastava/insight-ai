
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.database import get_db
from app.models.org import Org
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
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

    # Every user gets a personal org + default workspace on signup
    # (Day 16) — nothing in this app is accessible outside a workspace,
    # so without this a new user couldn't upload anything. Mirrors the
    # backfill given to pre-existing users (see docs/ADR.md ADR-011).
    org = Org(name=f"{user_data.email}'s Organization")
    db.add(org)
    db.flush()

    workspace = Workspace(org_id=org.id, name="Default")
    db.add(workspace)
    db.flush()

    hashed = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed, org_id=org.id)
    db.add(new_user)
    db.flush()

    db.add(WorkspaceMember(user_id=new_user.id, workspace_id=workspace.id, role="owner"))

    db.commit()
    db.refresh(new_user)
    return{
        "message": "User created successfully", "user_id": new_user.id
    }
#whats happening up we are chekcing if a user with existing mail already exists if yes return error if no create a new user and commit it into the datwbase
@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, str(user.hashed_password)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer"
    }