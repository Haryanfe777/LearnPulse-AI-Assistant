"""Shared utilities.""" 
import re

def sanitize_text(text: str) -> str:
    """Clean and normalize text for safe output.
    
    Preserves UTF-8 characters (accents, emojis, etc.) while removing
    control characters that could break JSON or terminal output.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Cleaned text with UTF-8 support
        
    Examples:
        >>> sanitize_text("José's score: 95% ⭐")
        "José's score: 95% ⭐"
        >>> sanitize_text(None)
        ""
    """
    if text is None:
        return ""
    
    try:
        # Convert to string if needed
        text = str(text)
        
        # Remove control characters (except newlines and tabs)
        # Control chars are 0x00-0x1F and 0x7F-0x9F
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # Normalize whitespace (collapse multiple spaces)
        text = re.sub(r'\s+', ' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    except Exception as e:
        # Fallback: return string representation
        return str(text)
