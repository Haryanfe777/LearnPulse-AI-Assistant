"""Vertex AI Gemini client utilities for text and chat interactions."""
from vertexai import init, generative_models
from app.core.config import PROJECT_ID, REGION, get_vertex_credentials
from app.utils.text import sanitize_text
from app.core.logging import get_logger
from typing import Dict
from functools import lru_cache

logger = get_logger(__name__)

@lru_cache(maxsize=2)  # Cache both Flash and Pro models
def get_model(model_name: str = "gemini-2.0-flash-exp"):
    """Initialize Vertex AI and return a Gemini model handle. Cached for performance.
    
    Using gemini-2.0-flash-exp for 3-5x faster responses.
    """
    creds = get_vertex_credentials()
    init(project=PROJECT_ID, location=REGION, credentials=creds)
    print(f"[Model Cache] Initializing {model_name}")
    return generative_models.GenerativeModel(model_name)

def generate_text(prompt: str):
    """One-shot text generation used for intent routing and utility prompts."""
    print("Sending prompt to Gemini...")
    try:
        model = get_model()
        generation_config = generative_models.GenerationConfig(
            temperature=0.9,
            top_p=0.95,
            top_k=40,
            max_output_tokens=512
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        print("Gemini responded successfully")
        return sanitize_text(response.text)
    except Exception as e:
        print("error: Assistant is unavailable right now. Please try again in a minute.", e)
        raise

# In-memory chat sessions keyed by session_id
_CHAT_SESSIONS: Dict[str, generative_models.ChatSession] = {}
# Track message count per session for summarization trigger
_SESSION_MESSAGE_COUNTS: Dict[str, int] = {}


def get_chat_session(session_id: str, system_instruction: str | None = None) -> generative_models.ChatSession:
    """Return (and cache) a Vertex chat session for a given session_id.

    When provided, the system_instruction is seeded as the first user message
    to establish stable behavior across the conversation.
    """
    if session_id in _CHAT_SESSIONS:
        return _CHAT_SESSIONS[session_id]

    model = get_model()
    history = []
    if system_instruction:
        # Seed chat by providing instruction as initial user content
        history = [
            generative_models.Content(
                role="user",
                parts=[generative_models.Part.from_text(system_instruction)],
            )
        ]
    chat = model.start_chat(history=history)
    _CHAT_SESSIONS[session_id] = chat
    return chat


def _summarize_conversation(chat_history: list) -> str:
    """Summarize a long conversation to reduce context window usage."""
    try:
        model = get_model()
        history_text = "\n\n".join([
            f"{'User' if i % 2 == 0 else 'Assistant'}: {turn.parts[0].text}" 
            for i, turn in enumerate(chat_history)
        ])
        
        prompt = f"""Summarize this LearnPulse AI assistant conversation, preserving key context:
- Student/class names mentioned
- Key metrics discussed (scores, trends, concepts)
- Important findings or recommendations
- Any ongoing questions or topics

Conversation:
{history_text[:10000]}  # Cap to avoid overwhelming the summarizer

Provide a concise summary (max 300 words) that captures essential context."""

        response = model.generate_content(prompt)
        summary = sanitize_text(response.text)
        print(f"[Summarization] Condensed {len(chat_history)} messages into summary")
        return summary
    except Exception as e:
        print(f"[Summarization] Failed: {e}")
        # Fallback: just return a simple truncation
        return f"[Previous conversation truncated after {len(chat_history)} messages]"


def chat_send_message(session_id: str, message: str, system_instruction: str | None = None) -> str:
    """Send a message on a per-session chat, return text response."""
    # Track message count
    _SESSION_MESSAGE_COUNTS[session_id] = _SESSION_MESSAGE_COUNTS.get(session_id, 0) + 1
    message_count = _SESSION_MESSAGE_COUNTS[session_id]
    
    # Log the message being sent
    logger.debug(
        f"Sending message to LLM",
        extra={
            "session_id": session_id[:8],
            "message_preview": message[:100] + "..." if len(message) > 100 else message,
            "message_length": len(message),
            "message_count": message_count
        }
    )
    
    # Check if we need to summarize (every 100 messages)
    if message_count > 0 and message_count % 100 == 0:
        logger.info(f"[Summarization] Triggering for session {session_id[:8]} at {message_count} messages")
        try:
            chat = _CHAT_SESSIONS.get(session_id)
            if chat and hasattr(chat, 'history') and len(chat.history) > 90:
                # Summarize first 90 messages
                summary = _summarize_conversation(chat.history[:90])
                
                # Create new session with summary as first message
                model = get_model()
                summary_content = generative_models.Content(
                    role="user",
                    parts=[generative_models.Part.from_text(f"[Conversation Summary]\n{summary}")]
                )
                
                # Keep recent 10 messages + summary
                new_history = [summary_content] + chat.history[90:]
                new_chat = model.start_chat(history=new_history)
                _CHAT_SESSIONS[session_id] = new_chat
                logger.info(f"[Summarization] Session refreshed: {len(chat.history)} → {len(new_history)} messages")
        except Exception as e:
            logger.warning(f"[Summarization] Error: {e}. Continuing with full history.")
    
    chat = get_chat_session(session_id=session_id, system_instruction=system_instruction)
    response = chat.send_message(message)
    
    # Monitor context window usage
    try:
        usage = response.usage_metadata
        total_tokens = usage.total_token_count
        logger.info(
            f"[Context Monitor] Session: {session_id[:8]}... | Tokens: {total_tokens:,} / 1,000,000 ({total_tokens/10000:.1f}%)",
            extra={
                "session_id": session_id[:8],
                "total_tokens": total_tokens,
                "input_tokens": usage.prompt_token_count,
                "output_tokens": usage.candidates_token_count
            }
        )
        
        # Warn if approaching limit (>800K tokens = 80%)
        if total_tokens > 800000:
            logger.warning(f"⚠️ WARNING: Session {session_id[:8]} approaching context limit!")
    except Exception as e:
        logger.debug(f"[Context Monitor] Could not read usage metadata: {e}")
    
    return sanitize_text(response.text)
