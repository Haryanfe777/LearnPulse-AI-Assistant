"""Async Vertex AI Gemini client utilities for non-blocking text and chat interactions.

Wraps synchronous Vertex AI SDK calls in async functions using thread pools
for non-blocking I/O in async FastAPI handlers.
"""
import asyncio
from vertexai import init, generative_models
from src.config import PROJECT_ID, REGION, get_vertex_credentials
from src.utils import sanitize_text
from typing import Dict, Optional
from functools import lru_cache

from src.logging_config import get_logger

logger = get_logger(__name__)

# Thread pool for blocking Vertex AI calls
_executor = None


def _get_executor():
    """Get or create thread pool executor for blocking calls."""
    global _executor
    if _executor is None:
        import concurrent.futures
        _executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="vertex_ai"
        )
    return _executor


@lru_cache(maxsize=2)  # Cache both Flash and Pro models
def get_model(model_name: str = "gemini-2.0-flash-exp"):
    """Initialize Vertex AI and return a Gemini model handle. Cached for performance.
    
    Using gemini-2.0-flash-exp for 3-5x faster responses (1-2s vs 3-6s).
    For complex analysis, can override with gemini-2.5-pro.
    """
    creds = get_vertex_credentials()
    init(project=PROJECT_ID, location=REGION, credentials=creds)
    logger.info(f"[Model Cache] Initializing {model_name}")
    return generative_models.GenerativeModel(model_name)


async def generate_text_async(prompt: str, max_output_tokens: int = 512) -> str:
    """Async one-shot text generation.
    
    Args:
        prompt: Input prompt
        max_output_tokens: Maximum tokens in response
        
    Returns:
        Generated text
        
    Raises:
        Exception: If generation fails
    """
    logger.debug("Sending prompt to Gemini (async)")
    
    try:
        # Run blocking call in thread pool
        loop = asyncio.get_event_loop()
        
        def _generate():
            model = get_model()
            generation_config = generative_models.GenerationConfig(
                temperature=0.9,
                top_p=0.95,
                top_k=40,
                max_output_tokens=max_output_tokens
            )
            response = model.generate_content(prompt, generation_config=generation_config)
            return response.text
        
        text = await loop.run_in_executor(_get_executor(), _generate)
        
        logger.debug("Gemini responded successfully (async)")
        return sanitize_text(text)
    
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}", exc_info=True)
        raise


# In-memory chat sessions keyed by session_id
_CHAT_SESSIONS: Dict[str, generative_models.ChatSession] = {}
# Track message count per session for summarization trigger
_SESSION_MESSAGE_COUNTS: Dict[str, int] = {}


async def get_chat_session_async(
    session_id: str,
    system_instruction: Optional[str] = None
) -> generative_models.ChatSession:
    """Return (and cache) a Vertex chat session for a given session_id.
    
    When provided, the system_instruction is seeded as the first user message
    to establish stable behavior across the conversation.
    
    Args:
        session_id: Unique session identifier
        system_instruction: Optional system instruction to seed chat
        
    Returns:
        Chat session object
    """
    if session_id in _CHAT_SESSIONS:
        return _CHAT_SESSIONS[session_id]
    
    # Run blocking initialization in thread pool
    loop = asyncio.get_event_loop()
    
    def _init_session():
        model = get_model()
        history = []
        if system_instruction:
            history = [
                generative_models.Content(
                    role="user",
                    parts=[generative_models.Part.from_text(system_instruction)],
                )
            ]
        chat = model.start_chat(history=history)
        _CHAT_SESSIONS[session_id] = chat
        return chat
    
    chat = await loop.run_in_executor(_get_executor(), _init_session)
    return chat


async def _summarize_conversation_async(chat_history: list) -> str:
    """Summarize a long conversation to reduce context window usage.
    
    Args:
        chat_history: List of chat messages
        
    Returns:
        Summary text
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _summarize():
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
{history_text[:10000]}

Provide a concise summary (max 300 words) that captures essential context."""

            response = model.generate_content(prompt)
            return response.text
        
        summary = await loop.run_in_executor(_get_executor(), _summarize)
        summary_text = sanitize_text(summary)
        
        logger.info(f"Conversation summarized: {len(chat_history)} messages condensed")
        return summary_text
    
    except Exception as e:
        logger.error(f"Summarization failed: {e}", exc_info=True)
        # Fallback: just return a simple truncation message
        return f"[Previous conversation truncated after {len(chat_history)} messages]"


async def chat_send_message_async(
    session_id: str,
    message: str,
    system_instruction: Optional[str] = None
) -> str:
    """Send a message on a per-session chat, return text response (async).
    
    Args:
        session_id: Session identifier
        message: User message
        system_instruction: Optional system instruction for new sessions
        
    Returns:
        Assistant response text
    """
    # Track message count
    _SESSION_MESSAGE_COUNTS[session_id] = _SESSION_MESSAGE_COUNTS.get(session_id, 0) + 1
    message_count = _SESSION_MESSAGE_COUNTS[session_id]
    
    # Check if we need to summarize (every 100 messages)
    if message_count > 0 and message_count % 100 == 0:
        logger.info(f"Triggering summarization for session {session_id[:8]} at {message_count} messages")
        
        try:
            chat = _CHAT_SESSIONS.get(session_id)
            if chat and hasattr(chat, 'history') and len(chat.history) > 90:
                # Summarize first 90 messages
                summary = await _summarize_conversation_async(chat.history[:90])
                
                # Create new session with summary as first message
                loop = asyncio.get_event_loop()
                
                def _create_new_session():
                    model = get_model()
                    summary_content = generative_models.Content(
                        role="user",
                        parts=[generative_models.Part.from_text(f"[Conversation Summary]\n{summary}")]
                    )
                    
                    # Keep recent 10 messages + summary
                    new_history = [summary_content] + chat.history[90:]
                    new_chat = model.start_chat(history=new_history)
                    _CHAT_SESSIONS[session_id] = new_chat
                    return len(new_history)
                
                new_len = await loop.run_in_executor(_get_executor(), _create_new_session)
                logger.info(f"Session refreshed: {len(chat.history)} → {new_len} messages")
        
        except Exception as e:
            logger.error(f"Summarization error: {e}. Continuing with full history.", exc_info=True)
    
    # Get or create chat session
    chat = await get_chat_session_async(session_id=session_id, system_instruction=system_instruction)
    
    # Send message in thread pool (blocking call)
    loop = asyncio.get_event_loop()
    
    def _send():
        response = chat.send_message(message)
        
        # Monitor context window usage
        try:
            usage = response.usage_metadata
            total_tokens = usage.total_token_count
            logger.info(
                f"Context usage: {total_tokens:,} / 1,000,000 tokens ({total_tokens/10000:.1f}%)",
                extra={"session_id": session_id[:8], "total_tokens": total_tokens}
            )
            
            # Warn if approaching limit (>800K tokens = 80%)
            if total_tokens > 800000:
                logger.warning(
                    f"Session {session_id[:8]} approaching context limit!",
                    extra={"total_tokens": total_tokens}
                )
        except Exception as e:
            logger.debug(f"Could not read usage metadata: {e}")
        
        return response.text
    
    text = await loop.run_in_executor(_get_executor(), _send)
    
    return sanitize_text(text)


# Backward compatibility: keep sync versions for any code that still needs them
def generate_text(prompt: str):
    """Synchronous version (deprecated, use generate_text_async)."""
    logger.warning("Using deprecated synchronous generate_text(). Migrate to generate_text_async().")
    
    try:
        model = get_model()
        generation_config = generative_models.GenerationConfig(
            temperature=0.9,
            top_p=0.95,
            top_k=40,
            max_output_tokens=512
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        return sanitize_text(response.text)
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}", exc_info=True)
        raise


def chat_send_message(session_id: str, message: str, system_instruction: Optional[str] = None) -> str:
    """Synchronous version (deprecated, use chat_send_message_async)."""
    logger.warning("Using deprecated synchronous chat_send_message(). Migrate to chat_send_message_async().")
    
    # Run async version in new event loop
    return asyncio.run(chat_send_message_async(session_id, message, system_instruction))

