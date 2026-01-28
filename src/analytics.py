from __future__ import annotations

"""Analytics helpers and grounding builders for the LearnPulse AI Instructor Assistant.

This module computes aggregates and compact text summaries that we pass to the LLM
to ground its reasoning. It also prepares small CSV tails for semantic hooks.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd

from src.data_loader import load_data
from src.config import STUDENT_COL, CLASS_COL, SCORE_COL


# ----------------
# HELPER FUNCTIONS
# ----------------

def _ensure_dataframe(df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Return provided DataFrame or load the default dataset once."""
    return df if df is not None else load_data()


def _safe_mean(series: pd.Series) -> float:
    """Mean with guards; returns NaN for empty series."""
    if series is None or series.empty:
        return float("nan")
    return float(series.mean())


def _format_pct(value: Optional[float]) -> str:
    """Format numeric values to one decimal (string), dash if missing."""
    if value is None:
        return "-"
    try:
        return f"{value:.1f}"
    except Exception:
        return "-"


# ----------------
# DATA FILTERING
# ----------------

def filter_df(df: pd.DataFrame, class_id: str|None=None, concept: str|None=None, timeframe: str|None=None) -> pd.DataFrame:
    """Filter DataFrame by class, concept, and/or timeframe.
    
    Args:
        df: DataFrame to filter
        class_id: Filter by class ID (case-insensitive)
        concept: Filter by concept (case-insensitive)
        timeframe: Filter by timeframe (e.g., "last 4 weeks")
    
    Returns:
        Filtered DataFrame
    """
    out = df.copy()
    if class_id and CLASS_COL in out.columns:
        out = out[out[CLASS_COL].astype(str).str.lower() == str(class_id).lower()]
    if concept and "concept" in out.columns:
        out = out[out["concept"].astype(str).str.lower() == concept.lower()]
    if timeframe and "week" in timeframe.lower() and "week_number" in out.columns:
        m = re.search(r"last\s+(\d+)\s*week", timeframe)
        if m:
            k = int(m.group(1))
            maxw = int(out["week_number"].max())
            out = out[out["week_number"] >= maxw - (k-1)]
    return out

# ----------------
# STATS AGGREGATION
# ----------------

def get_multi_student_stats(names: list[str], df: pd.DataFrame|None=None) -> list[dict]:
    """Get stats for multiple students at once.
    
    Args:
        names: List of student names
        df: Optional DataFrame (uses default if not provided)
    
    Returns:
        List of student stats dictionaries
    """
    data = _ensure_dataframe(df)
    return [get_student_stats(n, data) for n in names]


def rank_students(df: pd.DataFrame|None=None, metric="average_score", top=5, class_id=None, concept=None, timeframe=None, reverse=True):
    """Rank students by a metric with optional filtering.
    
    Args:
        df: Optional DataFrame
        metric: Metric to rank by (default: "average_score")
        top: Number of top students to return
        class_id: Filter by class
        concept: Filter by concept
        timeframe: Filter by timeframe
        reverse: Sort descending (default: True for highest first)
    
    Returns:
        List of ranked student dictionaries
    """
    data = filter_df(_ensure_dataframe(df), class_id, concept, timeframe)
    if STUDENT_COL not in data.columns or SCORE_COL not in data.columns:
        return []
    agg = (
        data.groupby(STUDENT_COL)[SCORE_COL]
        .mean()
        .reset_index()
        .rename(columns={SCORE_COL: "average_score"})
        .sort_values(metric, ascending=not reverse)
        .head(top)
    )
    return agg.to_dict(orient="records")


def get_student_stats(student_name: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Return core analytics for a single student:
    - session counts
    - score aggregates
    - weekly trend (by week_number if present)
    - concept breakdown
    - recent feedback notes (if present)
    """
    data = _ensure_dataframe(df)
    lower_col = f"{STUDENT_COL}_lower"
    col = lower_col if lower_col in data.columns else STUDENT_COL
    sdf = data[data[col].astype(str).str.lower() == str(student_name).lower()]
    if sdf.empty:
        return {"student": student_name, "exists": False}

    stats: Dict[str, Any] = {
        "student": student_name,
        "exists": True,
        "total_sessions": int(len(sdf)),
        "average_score": _safe_mean(sdf[SCORE_COL]) if SCORE_COL in sdf.columns else None,
        "median_score": float(sdf[SCORE_COL].median()) if SCORE_COL in sdf.columns else None,
        "best_score": float(sdf[SCORE_COL].max()) if SCORE_COL in sdf.columns else None,
        "worst_score": float(sdf[SCORE_COL].min()) if SCORE_COL in sdf.columns else None,
    }

    # Optional fields
    if "attempts" in sdf.columns:
        stats["total_attempts"] = int(sdf["attempts"].sum())
    if "success_rate" in sdf.columns:
        stats["avg_success_rate"] = float(sdf["success_rate"].mean())
    if "interaction_accuracy" in sdf.columns:
        stats["avg_interaction_accuracy"] = float(sdf["interaction_accuracy"].mean())
    if "streak_days" in sdf.columns:
        stats["max_streak_days"] = int(sdf["streak_days"].max())

    # Trends by ISO week number if available
    if "week_number" in sdf.columns and SCORE_COL in sdf.columns:
        by_week = (
            sdf.groupby("week_number")
            .agg(**{SCORE_COL: (SCORE_COL, "mean"), "count": (SCORE_COL, "size")})
            .reset_index()
            .sort_values("week_number")
        )
        stats["trend_by_week"] = by_week.to_dict(orient="records")

    # Concept breakdown
    if "concept" in sdf.columns and SCORE_COL in sdf.columns:
        concept = (
            sdf.groupby("concept")
            .agg(avg_score=(SCORE_COL, "mean"), sessions=("concept", "count"))
            .reset_index()
            .sort_values("avg_score", ascending=True)
        )
        stats["concept_breakdown"] = concept.to_dict(orient="records")

    # Recent feedback notes
    if "feedback_notes" in sdf.columns:
        non_empty = sdf["feedback_notes"].dropna().astype(str).str.strip()
        notes = non_empty[non_empty != ""].tail(3).tolist()
        if notes:
            stats["recent_feedback_notes"] = notes

    return stats


def get_class_trends(class_id: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Return analytics for a class:
    - unique students
    - average score
    - weekly trend (mean score)
    - concept distribution
    """
    data = _ensure_dataframe(df)
    if CLASS_COL in data.columns:
        col = data[CLASS_COL].astype(str).str.lower()
        cdf = data[col == str(class_id).lower()]
    else:
        cdf = data.copy()
    if cdf.empty:
        return {"class_id": class_id, "exists": False}

    out: Dict[str, Any] = {
        "class_id": class_id,
        "exists": True,
        "total_sessions": int(len(cdf)),
        "total_students": int(cdf[STUDENT_COL].nunique()) if STUDENT_COL in cdf.columns else 0,
        "average_score": _safe_mean(cdf[SCORE_COL]) if SCORE_COL in cdf.columns else None,
    }

    if "week_number" in cdf.columns and SCORE_COL in cdf.columns:
        weekly = (
            cdf.groupby("week_number")
            .agg(**{SCORE_COL: (SCORE_COL, "mean"), "count": (SCORE_COL, "size")})
            .reset_index()
            .sort_values("week_number")
        )
        out["trend_by_week"] = weekly.to_dict(orient="records")

    if "concept" in cdf.columns and SCORE_COL in cdf.columns:
        concept = (
            cdf.groupby("concept")
            .agg(avg_score=(SCORE_COL, "mean"), sessions=("concept", "count"))
            .reset_index()
            .sort_values("avg_score", ascending=True)
        )
        out["concept_breakdown"] = concept.to_dict(orient="records")

    return out


def compare_students(a: str, b: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Compare two students on basic aggregates and concept areas.
    """
    data = _ensure_dataframe(df)
    a_stats = get_student_stats(a, data)
    b_stats = get_student_stats(b, data)
    comparison: Dict[str, Any] = {"left": a_stats, "right": b_stats}
    if a_stats.get("exists") and b_stats.get("exists"):
        left = a_stats.get("average_score")
        right = b_stats.get("average_score")
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            comparison["delta_avg_score"] = float(left - right)
    return comparison


def _summarize_student_stats(stats: Dict[str, Any]) -> str:
    if not stats.get("exists"):
        return f"No data found for learner '{stats.get('student')}'."
    lines: List[str] = []
    lines.append(f"Learner: {stats['student']}")
    lines.append(f"- Sessions: {stats.get('total_sessions')}")
    lines.append(f"- Avg score: {_format_pct(stats.get('average_score'))}")
    if "median_score" in stats:
        lines.append(f"- Median score: {_format_pct(stats.get('median_score'))}")
    if "best_score" in stats and "worst_score" in stats:
        lines.append(f"- Best/Worst: {_format_pct(stats.get('best_score'))} / {_format_pct(stats.get('worst_score'))}")
    if "avg_success_rate" in stats:
        lines.append(f"- Avg success_rate: {_format_pct(stats.get('avg_success_rate') * 100)}%")
    if "avg_interaction_accuracy" in stats:
        lines.append(f"- Avg interaction_accuracy: {_format_pct(stats.get('avg_interaction_accuracy') * 100)}%")
    if "max_streak_days" in stats:
        lines.append(f"- Max streak days: {stats.get('max_streak_days')}")
    if stats.get("trend_by_week"):
        # show recent 4 weeks
        recent = stats["trend_by_week"][-4:]
        parts = [f"W{int(x['week_number'])}:{_format_pct(float(x.get(SCORE_COL, 0)))}"
                 for x in recent]
        lines.append(f"- Recent weekly avg: {', '.join(parts)}")
    if stats.get("concept_breakdown"):
        worst = sorted(stats["concept_breakdown"], key=lambda d: d.get("avg_score", float("inf")))[:1]
        if worst:
            lines.append(f"- Lowest concept: {worst[0]['concept']} (avg {_format_pct(worst[0]['avg_score'])})")
    if stats.get("recent_feedback_notes"):
        lines.append("- Recent notes: " + " | ".join(stats["recent_feedback_notes"]))
    return "\n".join(lines)


def _summarize_class_trends(trends: Dict[str, Any]) -> str:
    if not trends.get("exists"):
        return f"No data found for class '{trends.get('class_id')}'."
    lines: List[str] = []
    lines.append(f"Class: {trends['class_id']}")
    lines.append(f"- Learners: {trends.get('total_students')} | Sessions: {trends.get('total_sessions')}")
    lines.append(f"- Avg score: {_format_pct(trends.get('average_score'))}")
    if trends.get("trend_by_week"):
        recent = trends["trend_by_week"][-4:]
        parts = [f"W{int(x['week_number'])}:{_format_pct(float(x.get(SCORE_COL, 0)))}"
                 for x in recent]
        lines.append(f"- Recent weekly avg: {', '.join(parts)}")
    if trends.get("concept_breakdown"):
        worst = sorted(trends["concept_breakdown"], key=lambda d: d.get("avg_score", float("inf")))[:1]
        best = sorted(trends["concept_breakdown"], key=lambda d: d.get("avg_score", float("-inf")), reverse=True)[:1]
        if worst:
            lines.append(f"- Lowest concept: {worst[0]['concept']} (avg {_format_pct(worst[0]['avg_score'])})")
        if best:
            lines.append(f"- Strongest concept: {best[0]['concept']} (avg {_format_pct(best[0]['avg_score'])})")
    return "\n".join(lines)


def prepare_grounding(
    question: str,
    student: Optional[str] = None,
    class_id: Optional[str] = None,
    rows_snapshot: Optional[pd.DataFrame] = None,
    rows_limit: int = 40,
) -> str:
    """
    Build a compact grounding text for the LLM:
    - human-readable analytics summary
    - small raw CSV snapshot (tail N rows) for semantic hooks
    """
    df = _ensure_dataframe()
    sections: List[str] = []

    # Keep headings minimal; the model is instructed not to echo these labels
    sections.append(f"Question: {question}")

    if student:
        stats = get_student_stats(student, df)
        sections.append(_summarize_student_stats(stats))
    elif class_id:
        trends = get_class_trends(class_id, df)
        sections.append(_summarize_class_trends(trends))

    try:
        snap_df = rows_snapshot if rows_snapshot is not None else (
            df if (not student and not class_id) else
            (df[df[STUDENT_COL].astype(str).str.lower() == student.lower()] if student else df[df[CLASS_COL].astype(str).str.lower() == str(class_id).lower()])
        )
        if snap_df is not None and not snap_df.empty:
            csv_text = snap_df.tail(rows_limit).to_csv(index=False)
            sections.append(csv_text)
    except Exception:
        # Snapshot is best-effort; ignore errors silently
        pass

    return "\n\n".join(sections)


def prepare_comparison_grounding(
    question: str,
    student_a: str,
    student_b: str,
    rows_limit: int = 60,
) -> str:
    """
    Build grounding for comparing two students:
    - concise stat lines for A and B
    - delta summary
    - combined raw CSV tail for both students
    """
    df = _ensure_dataframe()
    a_stats = get_student_stats(student_a, df)
    b_stats = get_student_stats(student_b, df)
    comp = compare_students(student_a, student_b, df)

    sections: List[str] = []
    sections.append(f"Question: {question}")
    sections.append(_summarize_student_stats(a_stats))
    sections.append(_summarize_student_stats(b_stats))
    if "delta_avg_score" in comp:
        sections.append(f"Delta avg score (A - B): {comp['delta_avg_score']:.1f}")

    try:
        mask = df[STUDENT_COL].astype(str).str.lower().isin([student_a.lower(), student_b.lower()])
        snap_df = df[mask].copy()
        if snap_df is not None and not snap_df.empty:
            csv_text = snap_df.tail(rows_limit).to_csv(index=False)
            sections.append(csv_text)
    except Exception:
        pass

    return "\n\n".join(sections)


def generate_individualized_feedback(student_name: str, df: pd.DataFrame = None) -> str:
    """
    Generate personalized, actionable feedback for a student based on their performance data.
    
    Args:
        student_name: Name of the student
        df: Optional DataFrame (uses default if not provided)
    
    Returns:
        Formatted feedback string with specific recommendations
    """
    stats = get_student_stats(student_name, df)
    if not stats.get("exists"):
        return "No data available for individualized feedback."
    
    feedback_lines = []
    
    # 1. Identify weakest concept
    if stats.get("concept_breakdown"):
        weak = sorted(stats["concept_breakdown"], key=lambda x: x.get("avg_score", 100))[:1]
        if weak and weak[0]["avg_score"] < 65:
            concept = weak[0]["concept"]
            score = weak[0]["avg_score"]
            feedback_lines.append(
                f"🎯 **Focus Area: {concept}** (current avg: {score:.1f})\n"
                f"   - Assign 2-3 beginner-level {concept} challenges this week\n"
                f"   - Encourage slower, more deliberate practice\n"
                f"   - Consider pairing with a peer who excels in {concept}"
            )
    
    # 2. Engagement / motivation check
    if stats.get("max_streak_days", 0) < 3:
        feedback_lines.append(
            f"📅 **Engagement Alert:** Only {stats.get('max_streak_days', 0)}-day streak\n"
            f"   - Set a goal: Practice 3 days in a row for a reward\n"
            f"   - Send a reminder/encouragement message\n"
            f"   - Check for access barriers (device, time, motivation)"
        )
    
    # 3. Interaction accuracy
    if stats.get("avg_interaction_accuracy", 1.0) < 0.65:
        feedback_lines.append(
            f"🧭 **Interaction Quality:** Interaction accuracy at {stats.get('avg_interaction_accuracy', 0)*100:.1f}%\n"
            f"   - Check device setup and focus\n"
            f"   - Model the activity steps with a short walkthrough\n"
            f"   - Allow extra time for guided practice"
        )
    
    # 4. Declining trend
    if stats.get("trend_by_week") and len(stats["trend_by_week"]) >= 3:
        recent = stats["trend_by_week"][-3:]
        if recent[-1].get(SCORE_COL, 0) < recent[0].get(SCORE_COL, 100) - 5:
            feedback_lines.append(
                f"📉 **Recent Decline:** Scores dropped from {recent[0].get(SCORE_COL, 0):.1f} (W{recent[0]['week_number']}) "
                f"to {recent[-1].get(SCORE_COL, 0):.1f} (W{recent[-1]['week_number']})\n"
                f"   - Have a brief check-in conversation\n"
                f"   - Temporarily lower challenge difficulty\n"
                f"   - Investigate external factors (stress, illness, conflicts)"
            )
    
    # 5. Positive reinforcement if doing well
    if not feedback_lines and stats.get("average_score", 0) > 70:
        feedback_lines.append(
            f"✨ **Keep it up!** {student_name} is performing well (avg: {stats['average_score']:.1f})\n"
            f"   - Challenge with advanced difficulty levels\n"
            f"   - Consider peer tutoring opportunities\n"
            f"   - Celebrate streak days and concept mastery publicly"
        )
    
    if not feedback_lines:
        feedback_lines.append(
            f"📚 **Continue current approach** - {student_name} is progressing steadily."
        )
    
    return "\n\n".join(feedback_lines)


def prepare_general_grounding(question: str, rows_limit: int = 60) -> str:
    """
    Build grounding for a general (no entity) question using the whole dataset.
    Includes overall aggregates, concept extremes, and recent weekly trend if present.
    """
    df = _ensure_dataframe()
    sections: List[str] = []
    sections.append(f"Question: {question}")

    lines: List[str] = []
    lines.append("Overall dataset")
    try:
        total_sessions = int(len(df))
        total_students = int(df[STUDENT_COL].nunique()) if STUDENT_COL in df.columns else 0
        avg_score = _safe_mean(df[SCORE_COL]) if SCORE_COL in df.columns else None
        lines.append(f"- Students: {total_students} | Sessions: {total_sessions}")
        lines.append(f"- Avg score: {_format_pct(avg_score)}")
        if "week_number" in df.columns and SCORE_COL in df.columns:
            weekly = df.groupby("week_number")[SCORE_COL].mean().reset_index().sort_values("week_number")
            recent = weekly.tail(4).to_dict(orient="records")
            parts = [f"W{int(x['week_number'])}:{_format_pct(float(x.get(SCORE_COL, 0)))}"
                     for x in recent]
            lines.append(f"- Recent weekly avg: {', '.join(parts)}")
        if "concept" in df.columns and SCORE_COL in df.columns:
            concept = (
                df.groupby("concept")
                .agg(avg_score=(SCORE_COL, "mean"), sessions=("concept", "count"))
                .reset_index()
                .sort_values("avg_score", ascending=True)
            )
            worst = concept.head(1).to_dict(orient="records")
            best = concept.tail(1).to_dict(orient="records")
            if worst:
                lines.append(f"- Lowest concept: {worst[0]['concept']} (avg {_format_pct(worst[0]['avg_score'])})")
            if best:
                lines.append(f"- Strongest concept: {best[0]['concept']} (avg {_format_pct(best[0]['avg_score'])})")
    except Exception:
        pass

    sections.append("\n".join(lines))

    try:
        csv_text = df.tail(rows_limit).to_csv(index=False)
        sections.append(csv_text)
    except Exception:
        pass

    return "\n\n".join(sections)

def prepare_multi_grounding(question: str, names: list[str], rows_limit=80) -> str:
    df = _ensure_dataframe()
    stats = get_multi_student_stats(names, df)
    lines = ["Question: " + question] + [_summarize_student_stats(s) for s in stats]
    try:
        mask = df[STUDENT_COL].astype(str).str.lower().isin([n.lower() for n in names])
        csv_text = df[mask].tail(rows_limit).to_csv(index=False)
        lines.append(csv_text)
    except Exception:
        pass
    return "\n\n".join(lines)

def prepare_ranking_grounding(question: str, class_id=None, concept=None, timeframe=None, rows_limit=80) -> str:
    df = filter_df(_ensure_dataframe(), class_id, concept, timeframe)
    lines = ["Question: " + question]
    try:
        top5 = rank_students(df, top=5, class_id=class_id, concept=concept, timeframe=timeframe)
        if top5:
            lines.append("Top 5 by average_score:\n" + "\n".join(f"- {r[STUDENT_COL]}: {r['average_score']:.1f}" for r in top5))
        csv_text = df.tail(rows_limit).to_csv(index=False)
        lines.append(csv_text)
    except Exception:
        pass
    return "\n\n".join(lines)
