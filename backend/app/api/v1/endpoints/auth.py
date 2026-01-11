"""Authentication endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

router = APIRouter()


class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    display_name: str


class LoginResponse(BaseModel):
    """Login response with tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@router.post("/register", status_code=201)
async def register(request: RegisterRequest):
    """
    Register a new user.

    This is a placeholder endpoint. Full implementation will include:
    - Create user in database
    - Hash passwords (if using password fallback)
    - Return success response
    """
    return {
        "message": "Registration endpoint - to be implemented",
        "email": request.email,
        "display_name": request.display_name,
    }


@router.post("/login", response_model=LoginResponse)
async def login():
    """
    Login with credentials.

    This is a placeholder endpoint. Full implementation will include:
    - Verify credentials
    - Generate JWT tokens
    - Return access and refresh tokens
    """
    raise HTTPException(
        status_code=501,
        detail="Login endpoint not yet implemented. Use passkey authentication."
    )


@router.post("/logout")
async def logout():
    """
    Logout user.

    This is a placeholder endpoint. Full implementation will include:
    - Invalidate tokens
    - Clear session
    """
    return {"message": "Logout endpoint - to be implemented"}


@router.get("/me")
async def get_current_user():
    """
    Get current authenticated user.

    This is a placeholder endpoint. Full implementation will include:
    - Verify JWT token
    - Return user information
    """
    raise HTTPException(
        status_code=401,
        detail="Authentication required"
    )
