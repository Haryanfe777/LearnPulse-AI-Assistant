"""Async FastAPI routes for the LearnPulse AI Instructor Assistant with auth & Redis.

Production-ready version with:
- Async/await for non-blocking I/O
- JWT authentication & RBAC authorization  
- Redis-backed session management
- Structured logging
- Request caching
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
import uuid
from typing import Optional, List
from difflib import get_close_matches
import os

from app.infrastructure.data_loader import get_student_data, get_class_summary, list_students, list_classes, get_student_data_with_suggestions
from app.services.assistant import chat_with_memory_async
from app.services.analytics import (
    prepare_grounding,
    prepare_comparison_grounding,
    prepare_general_grounding,
    prepare_multi_grounding,
    prepare_ranking_grounding,
    generate_individualized_feedback,
)
from app.services.reports import (
    generate_student_report_html,
    generate_student_report_pdf,
    generate_class_report_html,
    generate_class_report_pdf,
)
from app.services.support import (
    detect_dissatisfaction,
    create_support_ticket,
    ESCALATION_THRESHOLD,
)
from app.core.auth import get_current_user, get_optional_user, User, LoginRequest, TokenResponse, authenticate_user, create_access_token, verify_class_access, verify_student_access
from app.infrastructure.redis import SessionStore, CacheManager, get_redis_client
from app.core.logging import get_logger, LogTimer

logger = get_logger(__name__)
router = APIRouter()

# Initialize Redis clients
try:
    redis_client = get_redis_client()
    session_store = SessionStore(redis_client=redis_client, ttl_days=7)
    cache = CacheManager(redis_client=redis_client, ttl_hours=1)
    logger.info("Redis clients initialized successfully")
except Exception as e:
    logger.warning(f"Redis unavailable, falling back to in-memory storage: {e}")
    session_store = None  # Fall back to stateless if Redis unavailable
    cache = None


# -----------------
# AUTHENTICATION
# -----------------

@router.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate user and return JWT token.
    
    Args:
        req: Login credentials
        
    Returns:
        JWT token and user info
        
    Example:
        POST /auth/login
        {"email": "instructor@school.com", "password": "password123"}
    """
    with LogTimer(logger, "user_authentication"):
        user = authenticate_user(req.email, req.password)
        
        if not user:
            logger.warning(f"Failed login attempt for {req.email}")
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password"
            )
        
        access_token = create_access_token(user)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=24 * 60 * 60,  # 24 hours in seconds
            user=user
        )


@router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info.
    
    Requires: Authentication
    """
    return current_user


# -----------------
# STUDENT ENDPOINTS
# -----------------

@router.get("/student/{name}")
async def student_summary(name: str, current_user: User = Depends(get_optional_user)):
    """Return analytics summary for a given student.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    with LogTimer(logger, f"student_summary:{name}"):
        # Check cache first
        cache_key = f"student_summary:{name}"
        if cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Returning cached summary for {name}")
                return cached
        
        # Get student data with fuzzy matching suggestions
        data, suggestions = get_student_data_with_suggestions(name)
        
        if data is None or data.empty:
            error_msg = f"No data found for student '{name}'."
            if suggestions:
                error_msg += f" Did you mean: {', '.join(suggestions)}?"
            
            logger.warning(f"Student not found: {name}. Suggestions: {suggestions}")
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": error_msg,
                    "suggestions": suggestions or []
                }
            )
        
        # Verify access (check which class the student belongs to)
        student_class = data[data.columns[data.columns.str.lower() == 'class_id'][0]].iloc[0] if any(data.columns.str.lower() == 'class_id') else None
        if student_class:
            verify_student_access(current_user, name, student_class)
        
        try:
            from app.services.analytics import get_student_stats
            stats = get_student_stats(name, data)
            
            result = {"student": name, "stats": stats}
            
            # Cache the result
            if cache:
                cache.set(cache_key, result, ttl_hours=1)
            
            return result
        
        except Exception as exc:
            logger.error(f"Failed to generate summary for {name}: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to generate summary: {str(exc)}")


@router.get("/feedback/student/{name}")
async def get_student_feedback(name: str, current_user: User = Depends(get_optional_user)):
    """Generate individualized feedback for a student.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    with LogTimer(logger, f"student_feedback:{name}"):
        # Get student data with suggestions
        data, suggestions = get_student_data_with_suggestions(name)
        
        if data is None or data.empty:
            error_msg = f"No data found for student '{name}'."
            if suggestions:
                error_msg += f" Did you mean: {', '.join(suggestions)}?"
            
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": error_msg,
                    "suggestions": suggestions or []
                }
            )
        
        # Verify access
        student_class = data[data.columns[data.columns.str.lower() == 'class_id'][0]].iloc[0] if any(data.columns.str.lower() == 'class_id') else None
        if student_class:
            verify_student_access(current_user, name, student_class)
        
        try:
            feedback = generate_individualized_feedback(name, data)
            return {"student": name, "feedback": feedback}
        except Exception as exc:
            logger.error(f"Failed to generate feedback for {name}: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to generate feedback: {str(exc)}")


# -----------------
# CLASS ENDPOINTS
# -----------------

@router.get("/class/{class_id}")
async def class_summary(class_id: str, current_user: User = Depends(get_optional_user)):
    """Return analytics summary for a class.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    with LogTimer(logger, f"class_summary:{class_id}"):
        # Verify access
        verify_class_access(current_user, class_id)
        
        # Check cache
        cache_key = f"class_summary:{class_id}"
        if cache:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Returning cached summary for class {class_id}")
                return cached
        
        data = get_class_summary(class_id)
        if data.empty:
            raise HTTPException(status_code=404, detail=f"No data found for class '{class_id}'")
        
        try:
            from app.services.analytics import get_class_trends
            trends = get_class_trends(class_id, data)
            
            result = {"class_id": class_id, "trends": trends}
            
            # Cache result
            if cache:
                cache.set(cache_key, result, ttl_hours=1)
            
            return result
        
        except Exception as exc:
            logger.error(f"Failed to generate class summary for {class_id}: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Failed to generate summary: {str(exc)}")


# -----------------
# REPORT ENDPOINTS
# -----------------

@router.get("/report/student/{name}/html", response_class=HTMLResponse)
async def get_student_report_html(name: str, current_user: User = Depends(get_optional_user)):
    """Generate and return HTML report for a student.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    try:
        # Verify access
        data = get_student_data(name)
        if data is not None and not data.empty:
            student_class = data[data.columns[data.columns.str.lower() == 'class_id'][0]].iloc[0] if any(data.columns.str.lower() == 'class_id') else None
            if student_class:
                verify_student_access(current_user, name, student_class)
        
        html = generate_student_report_html(name)
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate HTML report for {name}: {exc}", exc_info=True)
        return HTMLResponse(
            content=f"<html><body><h1>Error generating report</h1><p>{exc}</p></body></html>",
            status_code=500
        )


@router.get("/report/student/{name}/pdf")
async def get_student_report_pdf(name: str, current_user: User = Depends(get_optional_user)):
    """Generate and download PDF report for a student.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    try:
        # Verify access
        data = get_student_data(name)
        if data is not None and not data.empty:
            student_class = data[data.columns[data.columns.str.lower() == 'class_id'][0]].iloc[0] if any(data.columns.str.lower() == 'class_id') else None
            if student_class:
                verify_student_access(current_user, name, student_class)
        
        pdf_buffer = generate_student_report_pdf(name)
        if pdf_buffer is None:
            raise HTTPException(status_code=500, detail="PDF generation unavailable. Install reportlab.")
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=student_report_{name.replace(' ', '_')}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate PDF report for {name}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(exc)}")


@router.get("/report/class/{class_id}/html", response_class=HTMLResponse)
async def get_class_report_html(class_id: str, current_user: User = Depends(get_optional_user)):
    """Generate and return HTML report for a class.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    try:
        verify_class_access(current_user, class_id)
        html = generate_class_report_html(class_id)
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate HTML report for class {class_id}: {exc}", exc_info=True)
        return HTMLResponse(
            content=f"<html><body><h1>Error generating report</h1><p>{exc}</p></body></html>",
            status_code=500
        )


@router.get("/report/class/{class_id}/pdf")
async def get_class_report_pdf(class_id: str, current_user: User = Depends(get_optional_user)):
    """Generate and download PDF report for a class.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    try:
        verify_class_access(current_user, class_id)
        pdf_buffer = generate_class_report_pdf(class_id)
        if pdf_buffer is None:
            raise HTTPException(status_code=500, detail="PDF generation unavailable. Install reportlab.")
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=class_report_{class_id}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to generate PDF report for class {class_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(exc)}")


# -----------------
# CHAT ENDPOINT
# -----------------

class ChatRequest(BaseModel):
    """Incoming chat payload from the UI."""
    message: str
    session_id: Optional[str] = None
    student: Optional[str] = None
    class_id: Optional[str] = None


# Lazy-loaded entity lists
_KNOWN_STUDENTS: Optional[List[str]] = None
_KNOWN_CLASSES: Optional[List[str]] = None


def _load_entities():
    """Lazy load known students and classes."""
    global _KNOWN_STUDENTS, _KNOWN_CLASSES
    if _KNOWN_STUDENTS is None:
        _KNOWN_STUDENTS = [s.lower() for s in list_students()]
    if _KNOWN_CLASSES is None:
        _KNOWN_CLASSES = [str(c).lower() for c in list_classes()]


@router.post("/chat")
async def chat_endpoint(req: ChatRequest, current_user: User = Depends(get_optional_user)):
    """Conversational endpoint with intent detection and context management.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    with LogTimer(logger, "chat_request"):
        base_session_id = req.session_id or str(uuid.uuid4())
        
        try:
            # Load or get session state from Redis
            if session_store:
                state = session_store.get(base_session_id)
                if not state:
                    state = {
                        "student": None,
                        "class_id": None,
                        "scope": None,
                        "compare_pair": None,
                        "multi_students": None,
                        "dissatisfaction_count": 0,
                        "conversation_history": [],
                        "escalated": False
                    }
            else:
                # Fallback to stateless
                state = {
                    "student": None,
                    "class_id": None,
                    "scope": None,
                    "dissatisfaction_count": 0,
                    "conversation_history": [],
                    "escalated": False
                }
            
            # Lazy-load known entities
            _load_entities()
            
            lower = req.message.lower()
            
            # Track conversation history
            state.setdefault("conversation_history", [])
            state["conversation_history"].append({"role": "user", "content": req.message})
            
            # Detect dissatisfaction
            is_dissatisfied = detect_dissatisfaction(req.message)
            if is_dissatisfied:
                state["dissatisfaction_count"] = state.get("dissatisfaction_count", 0) + 1
                logger.info(f"Dissatisfaction detected in session {base_session_id}, count: {state['dissatisfaction_count']}")
            
            # Auto-escalate if threshold reached and not already escalated
            if state.get("dissatisfaction_count", 0) >= ESCALATION_THRESHOLD and not state.get("escalated"):
                logger.warning(f"Escalation threshold reached for session {base_session_id}, creating support ticket")
                
                # Create support ticket
                smtp_host = os.getenv("SMTP_HOST")
                smtp_config = None
                if smtp_host:
                    smtp_config = {
                        "host": smtp_host,
                        "port": int(os.getenv("SMTP_PORT", 587)),
                        "username": os.getenv("SMTP_USERNAME"),
                        "password": os.getenv("SMTP_PASSWORD"),
                        "from_email": os.getenv("SMTP_FROM_EMAIL", "support@learnpulse.ai")
                    }

                ticket_result = create_support_ticket(
                    session_id=base_session_id,
                    user_info={
                        "email": current_user.email,
                        "name": getattr(current_user, "name", current_user.email.split("@")[0]),
                        "user_id": current_user.user_id,
                        "role": current_user.role
                    },
                    conversation_history=state["conversation_history"],
                    issue_summary=f"Instructor dissatisfaction after {state['dissatisfaction_count']} signals",
                    smtp_config=smtp_config
                )
                
                state["escalated"] = True
                
                # Save state before returning
                if session_store:
                    session_store.set(base_session_id, state)
                
                # Check if ticket creation succeeded
                if ticket_result.get("success"):
                    # Success: provide ticket ID
                    ticket_id = ticket_result.get("ticket_id")
                    escalation_message = (
                        "I understand this isn't meeting your needs. I've connected you with our support team "
                        f"who will provide more personalized assistance. Your ticket ID is: {ticket_id}. "
                        "They'll reach out to you shortly at your registered email address."
                    )
                    logger.info(f"Support ticket created successfully: {ticket_id}")
                else:
                    # Failure: acknowledge issue without misleading ticket ID
                    error_msg = ticket_result.get("error", "Unknown error")
                    escalation_message = (
                        "I understand this isn't meeting your needs. I've attempted to connect you with our support team, "
                        "but encountered a technical issue. Please contact the support team for follow-up. "
                        "and reference your session for faster assistance."
                    )
                    logger.error(
                        f"Failed to create support ticket for session {base_session_id}: {error_msg}",
                        extra={"session_id": base_session_id, "error": error_msg}
                    )
                
                state["conversation_history"].append({"role": "assistant", "content": escalation_message})
                
                return {
                    "session_id": base_session_id,
                    "reply": escalation_message,
                    "escalated": True,
                    "ticket_created": ticket_result.get("success", False),
                    "ticket_id": ticket_result.get("ticket_id") if ticket_result.get("success") else None
                }
            
            # Simple intent detection (heuristics-based for performance)
            def simple_intent_detection(message, students, classes):
                lower_msg = message.lower()
                found_students = [s for s in students if s and s in lower_msg]
                found_class = next((c for c in classes if c and c in lower_msg), None)
                
                is_compare = any(kw in lower_msg for kw in ['compare', 'vs', 'versus', 'difference between'])
                is_ranking = any(kw in lower_msg for kw in ['rank', 'top', 'best', 'worst', 'lowest', 'highest'])
                
                if is_compare and len(found_students) >= 2:
                    intent_type = 'compare_query'
                elif is_ranking:
                    intent_type = 'ranking_query'
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
                    'students': found_students[:5],
                    'class_id': found_class
                }
            
            intent = simple_intent_detection(req.message, _KNOWN_STUDENTS, _KNOWN_CLASSES)
            intent_type = intent.get("intent", "general_query")
            
            # Detect entities
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
            
            class_id = req.class_id or intent.get("class_id") or detected_class or state.get("class_id")
            
            # Resolve intent and prepare grounding
            intent_students = [s.lower() for s in intent.get("students", []) if isinstance(s, str)]
            
            def resolve_name(name: str) -> Optional[str]:
                if not name or name in _KNOWN_STUDENTS:
                    return name
                match = get_close_matches(name, _KNOWN_STUDENTS, n=1, cutoff=0.8)
                return match[0] if match else None
            
            resolved_from_intent = [resolve_name(s) for s in intent_students]
            resolved_from_intent = [s for s in resolved_from_intent if s]
            
            student = None
            compare_pair = None
            multi_students = None
            
            if intent_type == "compare_query" and len(resolved_from_intent) >= 2:
                compare_pair = (resolved_from_intent[0], resolved_from_intent[1])
            elif intent_type == "multi_student_query" and len(resolved_from_intent) >= 2:
                multi_students = resolved_from_intent[:5]
            elif intent_type == "student_query" and resolved_from_intent:
                student = resolved_from_intent[0]
            elif detected_students:
                student = detected_students[0]
            else:
                # Reuse last scope for follow-ups
                if state.get("scope") == "student":
                    student = state.get("student")
                elif state.get("scope") == "class":
                    class_id = state.get("class_id")
            
            # Determine context type
            if compare_pair:
                context_type = "compare"
            elif multi_students:
                context_type = "multi"
            elif student:
                context_type = "student"
            elif class_id:
                context_type = "class"
            else:
                context_type = "general"
            
            # Prepare grounding
            supplemental = None
            if compare_pair:
                supplemental = prepare_comparison_grounding(
                    question=req.message,
                    student_a=compare_pair[0],
                    student_b=compare_pair[1],
                    rows_limit=60
                )
            elif multi_students:
                supplemental = prepare_multi_grounding(
                    question=req.message,
                    names=multi_students,
                    rows_limit=80
                )
            elif student:
                df = get_student_data(student)
                if df is not None and not df.empty:
                    supplemental = prepare_grounding(question=req.message, student=student, rows_snapshot=df, rows_limit=40)
            elif class_id:
                df = get_class_summary(class_id)
                supplemental = prepare_grounding(question=req.message, class_id=class_id, rows_snapshot=df, rows_limit=50)
            else:
                supplemental = prepare_general_grounding(question=req.message, rows_limit=60)
            
            # Send to LLM (async)
            reply = await chat_with_memory_async(
                session_id=base_session_id,
                message=req.message,
                supplemental_context=supplemental,
                context_type=context_type
            )
            
            # Add assistant's reply to conversation history
            state["conversation_history"].append({"role": "assistant", "content": reply})
            
            # Keep only last 50 messages to avoid memory bloat
            if len(state["conversation_history"]) > 50:
                state["conversation_history"] = state["conversation_history"][-50:]
            
            # Update session state
            state["scope"] = context_type
            state["student"] = student if context_type == "student" else state.get("student")
            state["class_id"] = class_id if context_type == "class" else state.get("class_id")
            state["compare_pair"] = list(compare_pair) if compare_pair else None
            state["multi_students"] = list(multi_students) if multi_students else None
            
            # Save session state to Redis
            if session_store:
                session_store.set(base_session_id, state)
            
            return {"session_id": base_session_id, "reply": reply}
        
        except Exception as exc:
            logger.error(f"Chat request failed: {exc}", exc_info=True)
            raise HTTPException(status_code=502, detail=f"Chat failed: {str(exc)}")


# -----------------
# METADATA ENDPOINTS
# -----------------

@router.get("/meta")
async def meta(current_user: User = Depends(get_optional_user)):
    """Return available student names and class ids.
    
    Authentication: Optional (demo mode enabled for unauthenticated requests)
    """
    students = list_students()
    classes = list_classes()
    return {"students": students, "class_ids": classes}


@router.get("/health")
async def health_check():
    """Health check endpoint (no auth required)."""
    health_status = {
        "status": "healthy",
        "redis": "connected" if (session_store and cache) else "unavailable"
    }
    return health_status

