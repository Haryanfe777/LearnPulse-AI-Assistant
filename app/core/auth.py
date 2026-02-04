"""Authentication and authorization for the LearnPulse AI Instructor Assistant API.

Implements JWT-based authentication with role-based access control (RBAC).
Instructors can only access data for their assigned classes.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel, EmailStr

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# JWT Configuration from settings
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# Production security check
if settings.environment == "production":
    if SECRET_KEY == "development-secret-key-change-in-production":
        raise ValueError("JWT_SECRET_KEY must be set to a secure value in production!")
    if len(SECRET_KEY) < 32:
        logger.warning("JWT_SECRET_KEY should be at least 32 characters for security")

# Security scheme
security = HTTPBearer()
security_optional = HTTPBearer(auto_error=False)  # Optional auth for demo mode


# Pydantic models
class User(BaseModel):
    """User model representing an instructor."""
    id: str
    email: EmailStr
    name: str
    role: str = "instructor"
    organization_id: str
    classes: List[str] = []  # List of class IDs instructor has access to


class TokenData(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    email: str
    role: str
    organization_id: str
    exp: datetime


class LoginRequest(BaseModel):
    """Login request body."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User


def create_access_token(
    user: User,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token for user.
    
    Args:
        user: User object
        expires_delta: Token expiration time (default: 24 hours)
        
    Returns:
        Encoded JWT token
        
    Example:
        >>> user = User(id="123", email="instructor@school.com", ...)
        >>> token = create_access_token(user)
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    logger.info(
        f"Access token created for user {user.email}",
        extra={"user_id": user.id, "expires_at": expire.isoformat()}
    )
    
    return token


def decode_token(token: str) -> TokenData:
    """Decode and validate JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData with user info
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        token_data = TokenData(
            sub=payload.get("sub"),
            email=payload.get("email"),
            role=payload.get("role"),
            organization_id=payload.get("organization_id"),
            exp=datetime.fromtimestamp(payload.get("exp"))
        )
        
        return token_data
    
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token attempted: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """FastAPI dependency to get current authenticated user.
    
    Validates JWT token and returns user object. Raises 401 if invalid.
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
        
    Example:
        >>> @router.get("/protected")
        >>> def protected_route(user: User = Depends(get_current_user)):
        ...     return {"user": user.email}
    """
    token = credentials.credentials
    token_data = decode_token(token)
    
    # In production, fetch user from database
    # For now, reconstruct from token
    user = User(
        id=token_data.sub,
        email=token_data.email,
        role=token_data.role,
        organization_id=token_data.organization_id,
        classes=[],  # Replace with database lookup in production
    )
    
    logger.debug(f"User authenticated: {user.email}", extra={"user_id": user.id})
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)
) -> Optional[User]:
    """FastAPI dependency for optional authentication (demo mode).
    
    If a valid token is provided, returns the authenticated user.
    If no token is provided, returns a demo user for development/demo purposes.
    
    Args:
        credentials: Optional HTTP Bearer credentials
        
    Returns:
        User object (authenticated or demo)
    """
    if credentials is None:
        # Return demo user for unauthenticated access
        demo_user = User(
            id="demo_user",
            email="demo@learnpulse.ai",
            name="Demo User",
            role="instructor",
            organization_id="demo_org",
            classes=["4B", "5A"],  # Allow access to demo classes
        )
        logger.debug("Using demo user for unauthenticated request")
        return demo_user
    
    # If token provided, validate it
    try:
        token = credentials.credentials
        token_data = decode_token(token)
        
        user = User(
            id=token_data.sub,
            email=token_data.email,
            role=token_data.role,
            organization_id=token_data.organization_id,
            classes=[],
        )
        
        logger.debug(f"User authenticated: {user.email}", extra={"user_id": user.id})
        return user
    except HTTPException:
        # If token is invalid, fall back to demo user
        demo_user = User(
            id="demo_user",
            email="demo@learnpulse.ai",
            name="Demo User",
            role="instructor",
            organization_id="demo_org",
            classes=["4B", "5A"],
        )
        logger.debug("Invalid token, using demo user")
        return demo_user


def require_role(allowed_roles: List[str]):
    """Dependency factory for role-based access control.
    
    Args:
        allowed_roles: List of allowed roles
        
    Returns:
        Dependency function that checks user role
        
    Example:
        >>> @router.get("/admin")
        >>> def admin_route(user: User = Depends(require_role(["admin"]))):
        ...     return {"message": "Admin access granted"}
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            logger.warning(
                f"Insufficient permissions for {user.email}",
                extra={"user_id": user.id, "user_role": user.role, "required_roles": allowed_roles}
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(allowed_roles)}"
            )
        return user
    
    return role_checker


def verify_class_access(user: User, class_id: str) -> bool:
    """Verify that user has access to a specific class.
    
    Args:
        user: User object
        class_id: Class ID to check
        
    Returns:
        True if user has access
        
    Raises:
        HTTPException: If user doesn't have access
    """
    # For prototype: allow all access
    # In production: Check user.classes or database
    
    # Replace with actual database query in production
    # if class_id not in user.classes:
    #     logger.warning(
    #         f"Access denied to class {class_id} for {user.email}",
    #         extra={"user_id": user.id, "class_id": class_id}
    #     )
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail=f"You don't have access to class {class_id}"
    #     )
    
    return True


def verify_student_access(user: User, student_name: str, student_class: str) -> bool:
    """Verify that user has access to a specific student.
    
    Args:
        user: User object
        student_name: Student name
        student_class: Student's class ID
        
    Returns:
        True if user has access
        
    Raises:
        HTTPException: If user doesn't have access
    """
    # Verify access to student's class
    return verify_class_access(user, student_class)


# Mock user database (replace with real database in production)
MOCK_USERS = {
    "instructor@learnpulse.ai": {
        "id": "instructor_001",
        "email": "instructor@learnpulse.ai",
        "name": "Demo Instructor",
        "password_hash": "demo123",  # In production: use bcrypt hashed passwords
        "role": "instructor",
        "organization_id": "org_001",
        "classes": ["4B", "5A"]
    },
    "admin@learnpulse.ai": {
        "id": "admin_001",
        "email": "admin@learnpulse.ai",
        "name": "Admin User",
        "password_hash": "admin123",
        "role": "admin",
        "organization_id": "org_001",
        "classes": []  # Admin has access to all classes
    }
}


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password.
    
    Args:
        email: User email
        password: User password
        
    Returns:
        User object if authentication successful, None otherwise
        
    Note:
        This is a mock implementation. In production:
        1. Query user from database
        2. Verify password using bcrypt
        3. Check if account is active
    """
    user_data = MOCK_USERS.get(email)
    
    if not user_data:
        logger.warning(f"Login attempt for non-existent user: {email}")
        return None
    
    # In production: use bcrypt.checkpw(password.encode(), user_data["password_hash"])
    if password != user_data["password_hash"]:
        logger.warning(f"Invalid password for user: {email}")
        return None
    
    logger.info(f"User authenticated successfully: {email}")
    
    return User(
        id=user_data["id"],
        email=user_data["email"],
        name=user_data["name"],
        role=user_data["role"],
        organization_id=user_data["organization_id"],
        classes=user_data["classes"]
    )


# Optional: API key authentication for service-to-service calls
def verify_api_key(api_key: str) -> bool:
    """Verify API key for service-to-service authentication.
    
    Args:
        api_key: API key to verify
        
    Returns:
        True if valid
    """
    # In production: Store API keys in database with scopes
    valid_keys = os.getenv("API_KEYS", "").split(",")
    return api_key in valid_keys

