"""Domain models for users and authentication."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """User model representing an instructor or admin.
    
    Attributes:
        user_id: Unique identifier for the user
        email: User's email address
        name: Full name
        role: User role (instructor, admin, etc.)
        organization_id: Organization this user belongs to
        classes: List of class IDs the instructor has access to
        created_at: Account creation timestamp
        is_active: Whether the account is active
    """
    user_id: str = Field(alias="id")
    email: EmailStr
    name: str
    role: str = "instructor"
    organization_id: str
    classes: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    is_active: bool = True
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "email": "instructor@school.com",
                "name": "Jane Smith",
                "role": "instructor",
                "organization_id": "org_456",
                "classes": ["4A", "4B", "5C"],
                "is_active": True
            }
        }


class TokenData(BaseModel):
    """JWT token payload data.
    
    Attributes:
        sub: Subject (user ID)
        email: User email
        role: User role
        organization_id: Organization ID
        exp: Token expiration time
        iat: Token issued at time
    """
    sub: str  # User ID
    email: str
    role: str
    organization_id: str
    exp: datetime
    iat: Optional[datetime] = None


class LoginRequest(BaseModel):
    """Login credentials request.
    
    Attributes:
        email: User's email address
        password: User's password
    """
    email: EmailStr
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "instructor@school.com",
                "password": "secure_password123"
            }
        }


class TokenResponse(BaseModel):
    """Authentication token response.
    
    Attributes:
        access_token: JWT access token
        token_type: Token type (always "bearer")
        expires_in: Token lifetime in seconds
        user: Authenticated user details
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User
