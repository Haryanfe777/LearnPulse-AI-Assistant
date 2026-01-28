"""FastAPI routes for the LearnPulse AI Instructor Assistant.

Includes simple summary endpoints and a conversational /chat endpoint that
routes intent, prepares grounding, and scopes chat memory per intent.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from src.data_loader import get_student_data, get_class_summary, list_students, list_classes, load_data
from src.assistant import summarize_student_progress, summarize_class_overview, chat_with_memory
from src.analytics import (
    prepare_grounding,
    prepare_comparison_grounding,
    prepare_general_grounding,
    prepare_multi_grounding,
    prepare_ranking_grounding,
    get_multi_student_stats,
    generate_individualized_feedback,
)
from src.report_generator import (
    generate_student_report_html,
    generate_student_report_pdf,
    generate_class_report_html,
    generate_class_report_pdf,
)
# from src.routes_intent import classify_intent  # DISABLED: Using simple heuristics for performance
from difflib import get_close_matches
from pydantic import BaseModel
import uuid
from typing import Dict, Optional

router = APIRouter()

@router.get("/student/{name}")
def student_summary(name: str):
    """Return a short LLM-generated summary for a given student."""
    data = get_student_data(name)
    if data is None:
        return {"error": f"No data found for student '{name}'"}
    try:
        summary = summarize_student_progress(name, data.to_dict(orient="records"))
        return {"student": name, "summary": summary}
    except Exception as exc:  # ensure JSON response even on backend errors
        return JSONResponse(status_code=502, content={"error": f"Failed to generate summary: {exc}"})

@router.get("/class/{class_id}")
def class_summary(class_id: str):
    """Return a short LLM-generated overview for a class."""
    data = get_class_summary(class_id)
    try:
        summary = summarize_class_overview(class_id, data.to_dict(orient="records"))
        return {"class_id": class_id, "summary": summary}
    except Exception as exc:  # ensure JSON response even on backend errors
        return JSONResponse(status_code=502, content={"error": f"Failed to generate class summary: {exc}"})

@router.get("/health")
def health_check():
    return {"status": "API is healthy"}


# -----------------
# FEEDBACK ENDPOINTS
# -----------------

@router.get("/feedback/student/{name}")
def get_student_feedback(name: str):
    """Generate individualized feedback for a student."""
    data = get_student_data(name)
    if data is None:
        return JSONResponse(status_code=404, content={"error": f"No data found for student '{name}'"})
    try:
        feedback = generate_individualized_feedback(name, data)
        return {"student": name, "feedback": feedback}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"Failed to generate feedback: {exc}"})


# -----------------
# REPORT ENDPOINTS
# -----------------

@router.get("/report/student/{name}/html", response_class=HTMLResponse)
def get_student_report_html(name: str):
    """Generate and return HTML report for a student."""
    try:
        html = generate_student_report_html(name)
        return HTMLResponse(content=html)
    except Exception as exc:
        return HTMLResponse(content=f"<html><body><h1>Error generating report</h1><p>{exc}</p></body></html>", status_code=500)


@router.get("/report/student/{name}/pdf")
def get_student_report_pdf(name: str):
    """Generate and download PDF report for a student."""
    try:
        pdf_buffer = generate_student_report_pdf(name)
        if pdf_buffer is None:
            return JSONResponse(status_code=500, content={"error": "PDF generation unavailable. Install reportlab."})
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=student_report_{name.replace(' ', '_')}.pdf"}
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Failed to generate PDF: {exc}"})


@router.get("/report/class/{class_id}/html", response_class=HTMLResponse)
def get_class_report_html(class_id: str):
    """Generate and return HTML report for a class."""
    try:
        html = generate_class_report_html(class_id)
        return HTMLResponse(content=html)
    except Exception as exc:
        return HTMLResponse(content=f"<html><body><h1>Error generating report</h1><p>{exc}</p></body></html>", status_code=500)


@router.get("/report/class/{class_id}/pdf")
def get_class_report_pdf(class_id: str):
    """Generate and download PDF report for a class."""
    try:
        pdf_buffer = generate_class_report_pdf(class_id)
        if pdf_buffer is None:
            return JSONResponse(status_code=500, content={"error": "PDF generation unavailable. Install reportlab."})
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=class_report_{class_id}.pdf"}
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"Failed to generate PDF: {exc}"})


class ChatRequest(BaseModel):
    """Incoming chat payload from the UI."""
    message: str
    session_id: str | None = None
    student: str | None = None
    class_id: str | None = None

# Very small in-process state for entity memory
_SESSION_STATE: Dict[str, Dict[str, Optional[str]]] = {}
_KNOWN_STUDENTS = None  # populated lazily from data
_KNOWN_CLASSES = None

@router.get("/meta")
def meta():
    """Return available student names and class ids from the dataset."""
    students = list_students()
    classes = list_classes()
    return {"students": students, "class_ids": classes}


@router.post("/chat")
def chat_endpoint(req: ChatRequest):
    """Conversational endpoint: detect intent, prepare grounding, and chat with scoped memory."""
    base_session_id = req.session_id or str(uuid.uuid4())
    supplemental = None
    try:
        # Resolve student/class using request, previous state, or quick detection
        state = _SESSION_STATE.setdefault(base_session_id, {"student": None, "class_id": None, "scope": None, "compare_pair": None, "multi_students": None})

        lower = req.message.lower()

        # Lazy-load known entities
        global _KNOWN_STUDENTS, _KNOWN_CLASSES
        if _KNOWN_STUDENTS is None:
            _KNOWN_STUDENTS = [s.lower() for s in list_students()]
        if _KNOWN_CLASSES is None:
            _KNOWN_CLASSES = [str(c).lower() for c in list_classes()]

        # PERFORMANCE: Use simple heuristics instead of LLM intent classification (saves 2-4 seconds!)
        # Simple name/keyword detection is sufficient - main LLM handles ambiguity
        def simple_intent_detection(message, students, classes):
            lower_msg = message.lower()
            found_students = [s for s in students if s and s in lower_msg]
            found_class = next((c for c in classes if c and c in lower_msg), None)
            
            is_compare = any(kw in lower_msg for kw in ['compare', 'vs', 'versus', 'difference between'])
            is_ranking = any(kw in lower_msg for kw in ['rank', 'top', 'best', 'worst', 'lowest', 'highest'])
            is_viz = any(kw in lower_msg for kw in ['chart', 'graph', 'plot', 'visualize', 'show me'])
            
            if is_compare and len(found_students) >= 2:
                intent_type = 'compare_query'
            elif is_ranking:
                intent_type = 'ranking_query'
            elif is_viz:
                intent_type = 'visualization_query'
            elif len(found_students) >= 3:
                intent_type = 'multi_student_query'
            elif found_students:
                intent_type = 'student_query'
            elif found_class:
                intent_type = 'class_query'
            else:
                intent_type = 'general_query'
            
            return {
                'intent': intent_type,
                'students': found_students[:5],  # Limit to 5
                'class_id': found_class,
                'concepts': [],
                'timeframe': None
            }
        
        intent = simple_intent_detection(req.message, _KNOWN_STUDENTS, _KNOWN_CLASSES)
        intent_type = intent.get("intent") or "general_query"

        # Detect students mentioned in the message with positions, then sort by occurrence order (heuristic fallback)
        student_hits = []
        for name in _KNOWN_STUDENTS:
            if name:
                pos = lower.find(name)
                if pos != -1:
                    student_hits.append((name, pos))
        student_hits.sort(key=lambda x: x[1])
        detected_students = [name for name, _ in student_hits]
        detected_class = None
        for cid in _KNOWN_CLASSES:
            if cid and cid in lower:
                detected_class = cid
                break

        # Start from explicit request values; prefer class mentioned now over stale student state
        class_id = req.class_id or intent.get("class_id") or detected_class or state.get("class_id")

        # Intent resolution: prefer router signals; fall back to heuristics
        # (intent_type already determined above for visualization check)
        intent_students = [s.lower() for s in intent.get("students", []) if isinstance(s, str)]
        intent_students = [s for s in intent_students if s]  # clean empties

        # Fuzzy resolve names if router provided ones not in known list
        def resolve_name(name: str) -> str | None:
            if not name:
                return None
            if name in _KNOWN_STUDENTS:
                return name
            match = get_close_matches(name, _KNOWN_STUDENTS, n=1, cutoff=0.8)
            return match[0] if match else None

        resolved_from_intent = [resolve_name(s) for s in intent_students]
        resolved_from_intent = [s for s in resolved_from_intent if s]

        # Heuristic fallback names
        detected_students = detected_students or []

        student = None
        compare_pair = None
        multi_students: list[str] | None = None
        ranking_params = None

        if intent_type == "compare_query" and not class_id and len(resolved_from_intent) >= 2:
            compare_pair = (resolved_from_intent[0], resolved_from_intent[1])
        elif intent_type == "multi_student_query" and not class_id and len(resolved_from_intent) >= 2:
            multi_students = resolved_from_intent[:5]
        elif intent_type == "student_query" and not class_id and len(resolved_from_intent) >= 1:
            student = req.student or resolved_from_intent[0]
        elif intent_type == "class_query" and class_id:
            pass  # handled below
        elif intent_type == "ranking_query":
            ranking_params = {
                "class_id": class_id,
                "concept": (intent.get("concepts") or [None])[0],
                "timeframe": intent.get("timeframe"),
            }
        else:
            # Fallback to heuristics
            if not class_id and len(detected_students) >= 2 and ("compare" in lower or "vs" in lower or "versus" in lower or "between" in lower):
                compare_pair = (detected_students[0], detected_students[1])
            elif not class_id and len(detected_students) == 1:
                student = req.student or detected_students[0]
            else:
                # No explicit entities: reuse last scope for true follow-ups
                if state.get("scope") == "compare" and state.get("compare_pair"):
                    compare_pair = tuple(state["compare_pair"])  # type: ignore
                elif state.get("scope") == "multi" and state.get("multi_students"):
                    multi_students = list(state["multi_students"])  # type: ignore
                elif state.get("scope") == "student" and state.get("student"):
                    student = state.get("student")
                elif state.get("scope") == "class" and state.get("class_id"):
                    class_id = state.get("class_id")
                else:
                    if not class_id:
                        student = req.student or state.get("student")

        # Update in-memory state
        state["class_id"] = class_id
        state["student"] = student

        # Determine context type for grounding (but use single session for full history)
        if compare_pair:
            context_type = "compare"
        elif multi_students:
            context_type = "multi"
        elif student:
            context_type = "student"
        elif class_id:
            context_type = "class"
        elif ranking_params is not None:
            context_type = "ranking"
        else:
            context_type = "general"
        
        # Use single session to maintain full conversation history
        # This allows Gemini to naturaly use prior context
        scoped_session_id = base_session_id

        # Persist scope and key participants for next-turn follow-ups
        state["scope"] = context_type
        state["compare_pair"] = list(compare_pair) if compare_pair else None
        state["multi_students"] = list(multi_students) if multi_students else None
        state["student"] = student if context_type == "student" else state.get("student")
        state["class_id"] = class_id if context_type == "class" else state.get("class_id")

        # Prepare grounding context based on resolved scope
        if compare_pair:
            supplemental = prepare_comparison_grounding(
                question=req.message,
                student_a=compare_pair[0],
                student_b=compare_pair[1],
                rows_limit=60,
            )
        elif multi_students:
            supplemental = prepare_multi_grounding(
                question=req.message,
                names=multi_students,
                rows_limit=80,
            )
        elif student:
            df = get_student_data(student)
            if df is not None and not df.empty:
                supplemental = prepare_grounding(question=req.message, student=student, rows_snapshot=df, rows_limit=40)
        elif class_id:
            df = get_class_summary(class_id)
            supplemental = prepare_grounding(question=req.message, class_id=class_id, rows_snapshot=df, rows_limit=50)
        elif ranking_params is not None:
            supplemental = prepare_ranking_grounding(
                question=req.message,
                class_id=ranking_params.get("class_id"),
                concept=ranking_params.get("concept"),
                timeframe=ranking_params.get("timeframe"),
                rows_limit=80,
            )
        else:
            supplemental = prepare_general_grounding(question=req.message, rows_limit=60)

        reply = chat_with_memory(session_id=scoped_session_id, message=req.message, supplemental_context=supplemental, context_type=context_type)
        # Return the base session id so the client UI remains stable
        return {"session_id": base_session_id, "reply": reply}
    except Exception as exc:
        return JSONResponse(status_code=502, content={"session_id": base_session_id, "error": f"Chat failed: {exc}"})

