"""Text utilities for sanitization and cleaning."""
import re


def sanitize_text(text: str) -> str:
    """Clean and normalize text for safe output.
    
    Preserves UTF-8 characters, newlines, and basic formatting while removing
    control characters that could break JSON or terminal output.
    
    Args:
        text: Input text to sanitize
        
    Returns:
        Cleaned text with UTF-8 support and preserved formatting
        
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
        
        # Remove control characters EXCEPT newlines (\n), carriage returns (\r), and tabs (\t)
        # Keep: \t (0x09), \n (0x0A), \r (0x0D)
        # Remove: 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F, 0x7F-0x9F
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # Collapse multiple spaces (but NOT newlines) into single space
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Collapse multiple consecutive newlines into max 2 (preserves paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip leading/trailing whitespace from each line
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Strip overall leading/trailing whitespace
        text = text.strip()
        
        return text
    except Exception as e:
        # Fallback: return string representation
        return str(text)
