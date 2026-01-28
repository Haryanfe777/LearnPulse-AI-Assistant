"""Domain models for students and educational data."""
from datetime import date, datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class StudentData(BaseModel):
    """Student performance data point.
    
    Represents a single session or activity record for a student.
    """
    student_name: str
    class_id: str
    concept: str
    score: float = Field(ge=0, le=100, description="Performance score 0-100")
    attempts: int = Field(ge=0, description="Number of attempts")
    success_rate: float = Field(ge=0, le=1, description="Success rate 0-1")
    interaction_accuracy: float = Field(ge=0, le=1, description="Interaction accuracy 0-1")
    streak_days: int = Field(ge=0, description="Consecutive days of activity")
    session_date: date
    timestamp: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "student_name": "Aisha",
                "class_id": "4B",
                "concept": "Debugging",
                "score": 76.5,
                "attempts": 5,
                "success_rate": 0.8,
                "interaction_accuracy": 0.92,
                "streak_days": 3,
                "session_date": "2024-10-15"
            }
        }


class StudentStats(BaseModel):
    """Aggregated statistics for a student.
    
    Contains computed metrics across all of a student's activities.
    """
    student_name: str
    total_sessions: int
    avg_score: float
    avg_attempts: float
    avg_success_rate: float
    avg_interaction_accuracy: float
    max_streak: int
    concepts_practiced: List[str]
    concept_breakdown: Dict[str, Dict[str, float]]
    trend_by_week: Dict[int, Dict[str, float]]
    first_session: Optional[date] = None
    last_session: Optional[date] = None


class ClassStats(BaseModel):
    """Aggregated statistics for a class.
    
    Contains computed metrics across all students in a class.
    """
    class_id: str
    total_students: int
    total_sessions: int
    avg_score: float
    avg_attempts: float
    avg_success_rate: float
    concepts_covered: List[str]
    concept_breakdown: Dict[str, Dict[str, float]]
    trend_by_week: Dict[int, Dict[str, float]]
    top_performers: List[str] = Field(default_factory=list)
    struggling_students: List[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    """Comparison result between two students.
    
    Contains side-by-side metrics and computed differences.
    """
    student_a: str
    student_b: str
    metrics: Dict[str, Dict[str, float]]  # {metric_name: {"a": val, "b": val, "delta": diff}}
    summary: str
    winner: Optional[str] = None  # Student with better overall performance


class StudentFeedback(BaseModel):
    """Individualized feedback for a student.
    
    Contains actionable recommendations based on performance data.
    """
    student_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_assessment: str
    strengths: List[str]
    areas_for_improvement: List[str]
    recommended_actions: List[str]
    next_concepts: List[str] = Field(default_factory=list)


class ChatMessage(BaseModel):
    """Chat message in a conversation.
    
    Used for tracking conversation history.
    """
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    """Chat session state.
    
    Maintains context across multiple conversation turns.
    """
    session_id: str
    user_id: Optional[str] = None
    student: Optional[str] = None
    class_id: Optional[str] = None
    scope: Optional[str] = None  # student, class, compare, multi, general
    compare_pair: Optional[tuple[str, str]] = None
    multi_students: Optional[List[str]] = None
    dissatisfaction_count: int = 0
    conversation_history: List[ChatMessage] = Field(default_factory=list)
    escalated: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
