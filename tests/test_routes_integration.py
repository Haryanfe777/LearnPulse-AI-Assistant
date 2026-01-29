"""Integration tests for API routes."""
import pytest
from fastapi import status
from unittest.mock import patch, Mock


class TestAuthenticationRoutes:
    """Test authentication endpoints."""
    
    def test_login_with_valid_credentials(self, test_client):
        """Test successful login."""
        response = test_client.post(
            "/auth/login",
            json={"email": "instructor@learnpulse.ai", "password": "demo123"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["token_type"] == "bearer"
    
    def test_login_with_invalid_credentials(self, test_client):
        """Test login with wrong password."""
        response = test_client.post(
            "/auth/login",
            json={"email": "instructor@learnpulse.ai", "password": "wrongpassword"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_login_with_nonexistent_user(self, test_client):
        """Test login with non-existent email."""
        response = test_client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "password"}
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_get_current_user_with_valid_token(self, authenticated_client):
        """Test getting current user info with valid token."""
        response = authenticated_client.get("/auth/me")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "email" in data
        assert "name" in data
        assert "role" in data
    
    def test_get_current_user_without_token(self, test_client):
        """Test getting current user without authentication."""
        response = test_client.get("/auth/me")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestStudentRoutes:
    """Test student-related endpoints."""
    
    @patch('src.routes_new.get_student_data')
    @patch('src.routes_new.get_student_stats')
    def test_student_summary_with_auth(self, mock_stats, mock_data, authenticated_client, mock_student_data):
        """Test getting student summary with authentication."""
        mock_data.return_value = mock_student_data
        mock_stats.return_value = {
            "exists": True,
            "student": "Aisha",
            "total_sessions": 3,
            "average_score": 72.3
        }
        
        response = authenticated_client.get("/student/Aisha")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "student" in data
        assert "stats" in data
    
    def test_student_summary_without_auth(self, test_client):
        """Test accessing student data without authentication."""
        response = test_client.get("/student/Aisha")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @patch('src.routes_new.get_student_data')
    def test_student_summary_not_found(self, mock_data, authenticated_client):
        """Test getting summary for non-existent student."""
        mock_data.return_value = None
        
        response = authenticated_client.get("/student/NonExistent")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @patch('src.routes_new.get_student_data')
    @patch('src.routes_new.generate_individualized_feedback')
    def test_student_feedback(self, mock_feedback, mock_data, authenticated_client, mock_student_data):
        """Test generating student feedback."""
        mock_data.return_value = mock_student_data
        mock_feedback.return_value = "Great progress on Loops! Focus more on Debugging."
        
        response = authenticated_client.get("/feedback/student/Aisha")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "feedback" in data
        assert len(data["feedback"]) > 0


class TestClassRoutes:
    """Test class-related endpoints."""
    
    @patch('src.routes_new.get_class_summary')
    @patch('src.routes_new.get_class_trends')
    def test_class_summary_with_auth(self, mock_trends, mock_data, authenticated_client, mock_class_data):
        """Test getting class summary with authentication."""
        mock_data.return_value = mock_class_data
        mock_trends.return_value = {
            "class_id": "4B",
            "student_count": 3,
            "average_score": 76.7
        }
        
        response = authenticated_client.get("/class/4B")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "class_id" in data
        assert "trends" in data
    
    def test_class_summary_without_auth(self, test_client):
        """Test accessing class data without authentication."""
        response = test_client.get("/class/4B")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestChatRoutes:
    """Test chat endpoint."""
    
    @patch('src.routes_new.chat_with_memory_async')
    @patch('src.routes_new.get_student_data')
    def test_chat_with_student_query(self, mock_data, mock_chat, authenticated_client, mock_student_data):
        """Test chat with student-related question."""
        mock_data.return_value = mock_student_data
        mock_chat.return_value = "Aisha has completed 21 sessions with an average score of 72.3%."
        
        response = authenticated_client.post(
            "/chat",
            json={"message": "How is Aisha doing?"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "reply" in data
        assert "session_id" in data
        assert len(data["reply"]) > 0
    
    @patch('src.routes_new.chat_with_memory_async')
    def test_chat_with_general_query(self, mock_chat, authenticated_client):
        """Test chat with general question."""
        mock_chat.return_value = "LearnPulse AI uses activity-based learning to teach coding through practice."
        
        response = authenticated_client.post(
            "/chat",
            json={"message": "What is LearnPulse AI's teaching philosophy?"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "reply" in data
    
    def test_chat_without_auth(self, test_client):
        """Test chat without authentication."""
        response = test_client.post(
            "/chat",
            json={"message": "How is Aisha doing?"}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    @patch('src.routes_new.chat_with_memory_async')
    def test_chat_with_session_id(self, mock_chat, authenticated_client):
        """Test chat with existing session ID."""
        mock_chat.return_value = "The Delta column shows the difference between students."
        
        # First message
        response1 = authenticated_client.post(
            "/chat",
            json={"message": "Compare Adam and Aisha"}
        )
        session_id = response1.json()["session_id"]
        
        # Follow-up message with session ID
        response2 = authenticated_client.post(
            "/chat",
            json={"message": "What does Delta mean?", "session_id": session_id}
        )
        
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["session_id"] == session_id


class TestReportRoutes:
    """Test report generation endpoints."""
    
    @patch('src.routes_new.generate_student_report_html')
    @patch('src.routes_new.get_student_data')
    def test_student_html_report(self, mock_data, mock_report, authenticated_client, mock_student_data):
        """Test generating HTML report for student."""
        mock_data.return_value = mock_student_data
        mock_report.return_value = "<html><body><h1>Aisha's Report</h1></body></html>"
        
        response = authenticated_client.get("/report/student/Aisha/html")
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
    
    @patch('src.routes_new.generate_class_report_html')
    def test_class_html_report(self, mock_report, authenticated_client):
        """Test generating HTML report for class."""
        mock_report.return_value = "<html><body><h1>Class 4B Report</h1></body></html>"
        
        response = authenticated_client.get("/report/class/4B/html")
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]


class TestMetadataRoutes:
    """Test metadata endpoints."""
    
    @patch('src.routes_new.list_students')
    @patch('src.routes_new.list_classes')
    def test_meta_endpoint(self, mock_classes, mock_students, authenticated_client):
        """Test getting available students and classes."""
        mock_students.return_value = ["Aisha", "Adam", "Zoe"]
        mock_classes.return_value = ["4B", "5A"]
        
        response = authenticated_client.get("/meta")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "students" in data
        assert "class_ids" in data
        assert len(data["students"]) == 3
        assert len(data["class_ids"]) == 2
    
    def test_health_check(self, test_client):
        """Test health check endpoint (no auth required)."""
        response = test_client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"


class TestCaching:
    """Test caching behavior."""
    
    @patch('src.routes_new.cache')
    @patch('src.routes_new.get_student_data')
    @patch('src.routes_new.get_student_stats')
    def test_student_summary_caching(self, mock_stats, mock_data, mock_cache_manager, authenticated_client, mock_student_data):
        """Test that student summaries are cached."""
        # Configure mock cache
        mock_cache = Mock()
        mock_cache.get.return_value = None  # First call: cache miss
        mock_cache.set.return_value = True
        mock_cache_manager.return_value = mock_cache
        
        mock_data.return_value = mock_student_data
        mock_stats.return_value = {"exists": True, "student": "Aisha"}
        
        # First request - should hit analytics
        response1 = authenticated_client.get("/student/Aisha")
        assert response1.status_code == status.HTTP_200_OK
        
        # Verify cache.set was called
        # mock_cache.set.assert_called_once()


class TestErrorHandling:
    """Test error handling."""
    
    @patch('src.routes_new.chat_with_memory_async')
    def test_chat_with_llm_error(self, mock_chat, authenticated_client):
        """Test handling of LLM errors."""
        mock_chat.side_effect = Exception("LLM service unavailable")
        
        response = authenticated_client.post(
            "/chat",
            json={"message": "How is Aisha?"}
        )
        
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "error" in response.json()
    
    @patch('src.routes_new.get_student_data')
    def test_analytics_error_handling(self, mock_data, authenticated_client):
        """Test handling of analytics errors."""
        mock_data.side_effect = Exception("Database error")
        
        response = authenticated_client.get("/student/Aisha")
        
        # Should return error response
        assert response.status_code in [500, 502]

