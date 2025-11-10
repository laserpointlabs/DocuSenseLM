"""
Authentication router for login and user management
"""
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from api.auth import verify_password, get_password_hash, create_access_token
from api.db import get_db_session
from api.db.schema import User
from api.middleware.auth import get_current_user, get_current_admin_user, get_current_usermgt_user
from typing import List
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


@router.post("/login", response_model=LoginResponse)
async def login(login_data: LoginRequest):
    """Authenticate user and return JWT token"""
    db = get_db_session()
    try:
        user = db.query(User).filter(User.username == login_data.username).first()
        
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        access_token = create_access_token(data={"sub": user.username})
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            username=user.username,
            role=user.role
        )
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else ""
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_usermgt_user)
):
    """Create a new user (requires usermgt or admin role)"""
    db = get_db_session()
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Validate role
        if user_data.role not in ["admin", "usermgt", "user"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be 'admin', 'usermgt', or 'user'"
            )
        
        # Create new user
        new_user = User(
            id=uuid.uuid4(),
            username=user_data.username,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return UserResponse(
            id=str(new_user.id),
            username=new_user.username,
            role=new_user.role,
            is_active=new_user.is_active,
            created_at=new_user.created_at.isoformat() if new_user.created_at else ""
        )
    finally:
        db.close()


@router.get("/users", response_model=List[UserResponse])
async def list_users(current_user: User = Depends(get_current_usermgt_user)):
    """List all users (requires usermgt or admin role)"""
    db = get_db_session()
    try:
        users = db.query(User).all()
        return [
            UserResponse(
                id=str(user.id),
                username=user.username,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at.isoformat() if user.created_at else ""
            )
            for user in users
        ]
    finally:
        db.close()

