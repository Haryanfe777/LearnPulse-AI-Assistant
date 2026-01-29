"""Unit tests for analytics functions."""
import pytest
import pandas as pd
from src.analytics import (
    get_student_stats,
    get_class_trends,
    compare_students,
    rank_students,
    filter_df,
    _safe_mean,
    _format_pct
)


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_safe_mean_with_valid_data(self):
        """Test safe_mean with valid series."""
        series = pd.Series([10, 20, 30, 40, 50])
        result = _safe_mean(series)
        assert result == 30.0
    
    def test_safe_mean_with_empty_series(self):
        """Test safe_mean with empty series."""
        series = pd.Series([])
        result = _safe_mean(series)
        assert pd.isna(result)
    
    def test_safe_mean_with_none(self):
        """Test safe_mean with None."""
        result = _safe_mean(None)
        assert pd.isna(result)
    
    def test_format_pct_with_valid_float(self):
        """Test format_pct with valid number."""
        assert _format_pct(75.6789) == "75.7"
        assert _format_pct(100.0) == "100.0"
        assert _format_pct(0.0) == "0.0"
    
    def test_format_pct_with_none(self):
        """Test format_pct with None."""
        assert _format_pct(None) == "-"


class TestGetStudentStats:
    """Test get_student_stats function."""
    
    def test_get_student_stats_with_valid_student(self, mock_student_data):
        """Test getting stats for existing student."""
        stats = get_student_stats("Aisha", mock_student_data)
        
        assert stats["exists"] is True
        assert stats["student"] == "Aisha"
        assert stats["total_sessions"] == 3
        assert "average_score" in stats
        assert "median_score" in stats
        assert "best_score" in stats
        assert "worst_score" in stats
    
    def test_get_student_stats_with_nonexistent_student(self, mock_student_data):
        """Test getting stats for non-existent student."""
        stats = get_student_stats("NonExistent", mock_student_data)
        
        assert stats["exists"] is False
        assert stats["student"] == "NonExistent"
    
    def test_get_student_stats_case_insensitive(self, mock_student_data):
        """Test case-insensitive student name matching."""
        stats_lower = get_student_stats("aisha", mock_student_data)
        stats_upper = get_student_stats("AISHA", mock_student_data)
        stats_mixed = get_student_stats("AiShA", mock_student_data)
        
        assert stats_lower["exists"] is True
        assert stats_upper["exists"] is True
        assert stats_mixed["exists"] is True
    
    def test_get_student_stats_with_empty_dataframe(self):
        """Test with empty dataframe."""
        empty_df = pd.DataFrame()
        stats = get_student_stats("Aisha", empty_df)
        
        # Should handle gracefully
        assert "student" in stats


class TestGetClassTrends:
    """Test get_class_trends function."""
    
    def test_get_class_trends_with_valid_class(self, mock_class_data):
        """Test getting trends for existing class."""
        trends = get_class_trends("4B", mock_class_data)
        
        assert "class_id" in trends
        assert "student_count" in trends
        assert trends["student_count"] == 3
        assert "average_score" in trends
    
    def test_get_class_trends_case_insensitive(self, mock_class_data):
        """Test case-insensitive class ID matching."""
        trends_lower = get_class_trends("4b", mock_class_data)
        trends_upper = get_class_trends("4B", mock_class_data)
        
        assert trends_lower["student_count"] == 3
        assert trends_upper["student_count"] == 3


class TestCompareStudents:
    """Test compare_students function."""
    
    def test_compare_students_with_valid_students(self, mock_class_data):
        """Test comparing two existing students."""
        comparison = compare_students("Aisha", "Adam", mock_class_data)
        
        assert "student_a" in comparison
        assert "student_b" in comparison
        assert comparison["student_a"]["name"] == "Aisha"
        assert comparison["student_b"]["name"] == "Adam"
    
    def test_compare_students_with_nonexistent_student(self, mock_class_data):
        """Test comparing with non-existent student."""
        comparison = compare_students("Aisha", "NonExistent", mock_class_data)
        
        # Should handle gracefully
        assert "student_a" in comparison
        assert "student_b" in comparison


class TestRankStudents:
    """Test rank_students function."""
    
    def test_rank_students_basic(self, mock_class_data):
        """Test basic ranking."""
        ranked = rank_students(mock_class_data, top=3)
        
        assert len(ranked) <= 3
        assert all("average_score" in student for student in ranked)
    
    def test_rank_students_descending_order(self, mock_class_data):
        """Test that ranking is in descending order."""
        ranked = rank_students(mock_class_data, top=3, reverse=True)
        
        if len(ranked) >= 2:
            # Verify descending order
            for i in range(len(ranked) - 1):
                assert ranked[i]["average_score"] >= ranked[i+1]["average_score"]
    
    def test_rank_students_with_class_filter(self, mock_class_data):
        """Test ranking with class filter."""
        ranked = rank_students(mock_class_data, class_id="4B", top=5)
        
        assert len(ranked) > 0


class TestFilterDf:
    """Test filter_df function."""
    
    def test_filter_by_class(self, mock_class_data):
        """Test filtering by class."""
        filtered = filter_df(mock_class_data, class_id="4B")
        
        assert not filtered.empty
        assert all(filtered["class_id"] == "4B")
    
    def test_filter_by_concept(self, mock_student_data):
        """Test filtering by concept."""
        filtered = filter_df(mock_student_data, concept="Loops")
        
        assert not filtered.empty
        assert all(filtered["concept"] == "Loops")
    
    def test_filter_by_multiple_criteria(self, mock_class_data):
        """Test filtering by multiple criteria."""
        filtered = filter_df(mock_class_data, class_id="4B", concept="Loops")
        
        assert not filtered.empty
        assert all(filtered["class_id"] == "4B")
        assert all(filtered["concept"] == "Loops")
    
    def test_filter_case_insensitive(self, mock_class_data):
        """Test case-insensitive filtering."""
        filtered_lower = filter_df(mock_class_data, class_id="4b")
        filtered_upper = filter_df(mock_class_data, class_id="4B")
        
        assert len(filtered_lower) == len(filtered_upper)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_dataframe(self):
        """Test functions with empty dataframe."""
        empty_df = pd.DataFrame()
        
        stats = get_student_stats("Aisha", empty_df)
        assert "student" in stats
        
        ranked = rank_students(empty_df)
        assert ranked == []
    
    def test_missing_columns(self):
        """Test with dataframe missing expected columns."""
        incomplete_df = pd.DataFrame({
            'student_name': ['Aisha'],
            'score': [75.0]
            # Missing class_id, concept, etc.
        })
        
        stats = get_student_stats("Aisha", incomplete_df)
        assert stats["exists"] is True
    
    def test_special_characters_in_names(self):
        """Test with special characters in student names."""
        special_df = pd.DataFrame({
            'student_name': ["José", "François", "María"],
            'score': [75.0, 80.0, 85.0],
            'student_name_lower': ["josé", "françois", "maría"]
        })
        
        stats = get_student_stats("José", special_df)
        assert stats["exists"] is True

