"""Data loading and simple aggregations from mock CSV.

Provides cached data loading and helper functions for student/class data retrieval.
All functions use case-insensitive matching for names and class IDs.
"""
import pandas as pd
from functools import lru_cache
from difflib import get_close_matches
from typing import Optional, List
from app.core.config import STUDENT_COL, CLASS_COL, SCORE_COL, DATE_COL

DATA_PATH = "mock_data/mock_game_logs.csv"

@lru_cache(maxsize=1)
def load_data():
    """Load the mock CSV once, add derived columns, and normalize schema."""
    df = pd.read_csv(DATA_PATH)
    if SCORE_COL not in df.columns:
        # scale success_rate & interaction_accuracy ∈ [0,1] to a 0-100 score
        df[SCORE_COL] = ((df.get("success_rate", 0.0) * 0.7) + (df.get("interaction_accuracy", 0.0) * 0.3)) * 100
    if DATE_COL not in df.columns:
        # fabricate dates
        df[DATE_COL] = pd.Timestamp.today().normalize()
    lower_col = f"{STUDENT_COL}_lower"
    if STUDENT_COL in df.columns and lower_col not in df.columns:
        df[lower_col] = df[STUDENT_COL].str.lower()
    return df


def get_student_data(name: str):
    """Return a DataFrame of rows for a given student (case-insensitive), or None if empty."""
    df = load_data()
    lower_col = f"{STUDENT_COL}_lower"
    col = lower_col if lower_col in df.columns else STUDENT_COL
    student_df = df[df[col].str.lower() == name.lower()]
    return student_df if not student_df.empty else None

def get_class_summary(class_id="4B"):
    """Return a DataFrame of rows for a given class id (case-insensitive)."""
    df = load_data()
    if CLASS_COL in df.columns:
        col = df[CLASS_COL].astype(str)
        return df[col.str.lower() == str(class_id).lower()]
    return df

def list_students(limit: int = 100):
    df = load_data()
    if STUDENT_COL in df.columns:
        return df[STUDENT_COL].dropna().astype(str).str.strip().unique().tolist()[:limit]
    return []

def list_classes(limit: int = 100):
    df = load_data()
    if CLASS_COL in df.columns:
        return df[CLASS_COL].dropna().astype(str).str.strip().unique().tolist()[:limit]
    return []


def find_closest_student_name(name: str, n: int = 3, cutoff: float = 0.6) -> List[str]:
    """Find closest matching student names using fuzzy string matching.
    
    Args:
        name: The student name to search for
        n: Maximum number of matches to return (default: 3)
        cutoff: Similarity threshold 0-1 (default: 0.6)
        
    Returns:
        List of closest matching student names
        
    Example:
        >>> find_closest_student_name("Aishaa")
        ['Aisha']
        >>> find_closest_student_name("Jon")
        ['John', 'Joan']
    """
    all_students = list_students()
    if not all_students:
        return []
    
    # Case-insensitive matching
    matches = get_close_matches(name.lower(), [s.lower() for s in all_students], n=n, cutoff=cutoff)
    
    # Return original cased names
    result = []
    for match in matches:
        # Find the original name that matches
        for student in all_students:
            if student.lower() == match:
                result.append(student)
                break
    
    return result


def get_student_data_with_suggestions(name: str) -> tuple[Optional[pd.DataFrame], Optional[List[str]]]:
    """Get student data with fuzzy name suggestions if not found.
    
    Args:
        name: Student name to search for
        
    Returns:
        Tuple of (data, suggestions) where:
        - data is the DataFrame if found, None otherwise
        - suggestions is a list of similar names if data is None, None otherwise
        
    Example:
        >>> data, suggestions = get_student_data_with_suggestions("Aishaa")
        >>> if data is None:
        ...     print(f"Did you mean: {', '.join(suggestions)}?")
    """
    data = get_student_data(name)
    if data is not None:
        return data, None
    
    # Student not found, provide suggestions
    suggestions = find_closest_student_name(name, n=3, cutoff=0.6)
    return None, suggestions

