"""Pytest configuration and shared fixtures."""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_student_data():
    """Mock student data for testing."""
    return pd.DataFrame({
        'student_id': [101, 101, 101],
        'student_name': ['Aisha', 'Aisha', 'Aisha'],
        'class_id': ['4B', '4B', '4B'],
        'concept': ['Loops', 'Conditionals', 'Debugging'],
        'score': [76.5, 82.3, 58.1],
        'attempts': [5, 3, 8],
        'success_rate': [0.80, 0.85, 0.55],
        'interaction_accuracy': [0.75, 0.80, 0.60],
        'week_number': [41, 41, 42]
    })


@pytest.fixture
def mock_class_data():
    """Mock class data for testing."""
    return pd.DataFrame({
        'student_id': [101, 102, 103],
        'student_name': ['Aisha', 'Adam', 'Zoe'],
        'class_id': ['4B', '4B', '4B'],
        'concept': ['Loops', 'Loops', 'Loops'],
        'score': [76.5, 82.3, 71.2],
        'week_number': [41, 41, 41]
    })


@pytest.fixture
def mock_vertex_response():
    """Mock Vertex AI response."""
    return "This is a mock response from the LLM."


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user."""
    from src.auth import User
    return User(
        id="test_user_001",
        email="test@learnpulse.ai",
        name="Test Instructor",
        role="instructor",
        organization_id="org_001",
        classes=["4B", "5A"]
    )


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for testing."""
    from src.auth import create_access_token
    from src.auth import User
    user = User(
        id="test_user_001",
        email="test@learnpulse.ai",
        name="Test Instructor",
        role="instructor",
        organization_id="org_001",
        classes=["4B"]
    )
    return create_access_token(user)


@pytest.fixture
def test_client():
    """FastAPI test client."""
    # Import after fixtures are set up
    from main import app
    return TestClient(app)


@pytest.fixture
def authenticated_client(test_client, mock_jwt_token):
    """Authenticated test client with JWT token."""
    test_client.headers = {"Authorization": f"Bearer {mock_jwt_token}"}
    return test_client


@pytest.fixture(autouse=True)
def mock_redis():
    """Auto-mock Redis for all tests to avoid needing real Redis."""
    with patch('src.redis_client.get_redis_client') as mock:
        mock_client = Mock()
        mock_client.get.return_value = None
        mock_client.set.return_value = True
        mock_client.setex.return_value = True
        mock_client.delete.return_value = 1
        mock_client.exists.return_value = False
        mock_client.ping.return_value = True
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture(autouse=True)
def mock_vertex_ai():
    """Auto-mock Vertex AI to avoid real API calls in tests."""
    with patch('src.vertex_client_async.generate_text_async') as mock_gen, \
         patch('src.vertex_client_async.chat_send_message_async') as mock_chat:
        mock_gen.return_value = "Mock LLM response"
        mock_chat.return_value = "Mock chat response"
        yield {"generate": mock_gen, "chat": mock_chat}

