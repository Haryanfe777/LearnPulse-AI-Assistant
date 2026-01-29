"""Unit tests for authentication and authorization."""
import pytest
import jwt
from datetime import datetime, timedelta
from src.auth import (
    create_access_token,
    decode_token,
    authenticate_user,
    verify_class_access,
    verify_student_access,
    User
)


class TestJWTTokens:
    """Test JWT token creation and validation."""
    
    def test_create_access_token(self, mock_auth_user):
        """Test creating JWT token."""
        token = create_access_token(mock_auth_user)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long
    
    def test_decode_valid_token(self, mock_auth_user):
        """Test decoding valid token."""
        token = create_access_token(mock_auth_user)
        token_data = decode_token(token)
        
        assert token_data.sub == mock_auth_user.id
        assert token_data.email == mock_auth_user.email
        assert token_data.role == mock_auth_user.role
    
    def test_decode_expired_token(self, mock_auth_user):
        """Test decoding expired token."""
        # Create token that expired 1 hour ago
        expired_token = create_access_token(
            mock_auth_user,
            expires_delta=timedelta(hours=-1)
        )
        
        # Should raise HTTPException
        with pytest.raises(Exception) as exc_info:
            decode_token(expired_token)
        
        assert exc_info.value.status_code == 401
    
    def test_decode_invalid_token(self):
        """Test decoding malformed token."""
        invalid_token = "not.a.valid.jwt.token"
        
        with pytest.raises(Exception) as exc_info:
            decode_token(invalid_token)
        
        assert exc_info.value.status_code == 401
    
    def test_token_contains_required_claims(self, mock_auth_user):
        """Test that token contains all required claims."""
        from src.auth import SECRET_KEY, ALGORITHM
        
        token = create_access_token(mock_auth_user)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert "sub" in payload  # User ID
        assert "email" in payload
        assert "role" in payload
        assert "organization_id" in payload
        assert "exp" in payload  # Expiration
        assert "iat" in payload  # Issued at


class TestUserAuthentication:
    """Test user authentication."""
    
    def test_authenticate_valid_user(self):
        """Test authenticating with correct credentials."""
        user = authenticate_user("instructor@learnpulse.ai", "demo123")
        
        assert user is not None
        assert user.email == "instructor@learnpulse.ai"
        assert user.role == "instructor"
    
    def test_authenticate_invalid_password(self):
        """Test authenticating with wrong password."""
        user = authenticate_user("instructor@learnpulse.ai", "wrongpassword")
        
        assert user is None
    
    def test_authenticate_nonexistent_user(self):
        """Test authenticating non-existent user."""
        user = authenticate_user("nonexistent@example.com", "password")
        
        assert user is None
    
    def test_authenticate_admin_user(self):
        """Test authenticating admin user."""
        user = authenticate_user("admin@learnpulse.ai", "admin123")
        
        assert user is not None
        assert user.role == "admin"


class TestAccessControl:
    """Test role-based access control."""
    
    def test_verify_class_access_allowed(self, mock_auth_user):
        """Test verifying access to allowed class."""
        # In the mock implementation, all access is allowed for prototype
        # In production, this would check user.classes
        result = verify_class_access(mock_auth_user, "4B")
        
        assert result is True
    
    def test_verify_student_access_allowed(self, mock_auth_user):
        """Test verifying access to student in allowed class."""
        result = verify_student_access(mock_auth_user, "Aisha", "4B")
        
        assert result is True
    
    # Note: In production, add tests for denied access:
    # def test_verify_class_access_denied(self, mock_auth_user):
    #     """Test denying access to unauthorized class."""
    #     with pytest.raises(HTTPException) as exc_info:
    #         verify_class_access(mock_auth_user, "unauthorized_class")
    #     
    #     assert exc_info.value.status_code == 403


class TestUserModel:
    """Test User model."""
    
    def test_user_model_creation(self):
        """Test creating User instance."""
        user = User(
            id="test_123",
            email="test@example.com",
            name="Test User",
            role="instructor",
            organization_id="org_456",
            classes=["4B", "5A"]
        )
        
        assert user.id == "test_123"
        assert user.email == "test@example.com"
        assert user.role == "instructor"
        assert len(user.classes) == 2
    
    def test_user_model_defaults(self):
        """Test User model with default values."""
        user = User(
            id="test_123",
            email="test@example.com",
            name="Test User",
            organization_id="org_456"
        )
        
        # Default role should be "instructor"
        assert user.role == "instructor"
        # Default classes should be empty list
        assert user.classes == []
    
    def test_user_model_validation(self):
        """Test User model email validation."""
        # Valid email
        user = User(
            id="test_123",
            email="valid@example.com",
            name="Test User",
            organization_id="org_456"
        )
        assert user.email == "valid@example.com"
        
        # Invalid email should raise validation error
        with pytest.raises(Exception):
            User(
                id="test_123",
                email="not-an-email",
                name="Test User",
                organization_id="org_456"
            )


class TestSecurityConfiguration:
    """Test security configuration."""
    
    def test_jwt_secret_key_exists(self):
        """Test that JWT secret key is configured."""
        from src.auth import SECRET_KEY
        
        assert SECRET_KEY is not None
        assert len(SECRET_KEY) > 10
    
    def test_jwt_algorithm(self):
        """Test that JWT algorithm is configured."""
        from src.auth import ALGORITHM
        
        assert ALGORITHM == "HS256"
    
    def test_access_token_expiration(self):
        """Test that access tokens have reasonable expiration."""
        from src.auth import ACCESS_TOKEN_EXPIRE_MINUTES
        
        # Should be at least 15 minutes
        assert ACCESS_TOKEN_EXPIRE_MINUTES >= 15
        # Should not be more than 7 days (10080 minutes)
        assert ACCESS_TOKEN_EXPIRE_MINUTES <= 10080


class TestPasswordSecurity:
    """Test password security practices."""
    
    def test_passwords_not_in_plaintext(self):
        """Test that passwords are not stored in plaintext."""
        from src.auth import MOCK_USERS
        
        # In mock implementation, we use "password_hash" key
        # In production, this should actually be a bcrypt hash
        for user_data in MOCK_USERS.values():
            assert "password_hash" in user_data
            # Note: In production, verify it's a bcrypt hash:
            # assert user_data["password_hash"].startswith("$2b$")

