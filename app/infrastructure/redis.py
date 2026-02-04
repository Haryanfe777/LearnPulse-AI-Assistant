"""Redis client for session management and caching.

Provides centralized Redis connections, session storage with TTL,
and caching for expensive analytics operations.

For Cloud Run with Memorystore:
- Set REDIS_HOST to the Memorystore instance IP
- Set REDIS_PASSWORD if authentication is enabled
- Ensure VPC connector is configured for Cloud Run
"""
import json
import redis
from typing import Any, Dict, Optional
from datetime import timedelta
from functools import wraps
import hashlib

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

# Redis connection pool (lazy initialization)
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


def get_redis_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    db: Optional[int] = None,
    password: Optional[str] = None,
    decode_responses: bool = True
) -> Optional[redis.Redis]:
    """Get or create Redis client with connection pooling.
    
    Uses settings from environment variables if not explicitly provided.
    Returns None if Redis is not available (graceful fallback).
    
    Args:
        host: Redis host (default from REDIS_HOST env)
        port: Redis port (default from REDIS_PORT env)
        db: Redis database number (default from REDIS_DB env)
        password: Redis password (default from REDIS_PASSWORD env)
        decode_responses: Whether to decode responses to strings
        
    Returns:
        Redis client instance or None if unavailable
    """
    global _redis_pool, _redis_client
    
    # Use settings if not explicitly provided
    host = host or settings.redis_host
    port = port or settings.redis_port
    db = db if db is not None else settings.redis_db
    password = password or settings.redis_password
    
    if _redis_client is None:
        logger.info(f"Initializing Redis connection pool: {host}:{port}")
        
        try:
            _redis_pool = redis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                max_connections=50,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            
            _redis_client = redis.Redis(connection_pool=_redis_pool)
            
            # Test connection
            _redis_client.ping()
            logger.info("Redis connection established successfully")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
            _redis_client = None
            return None
        except Exception as e:
            logger.error(f"Redis initialization error: {e}", exc_info=True)
            _redis_client = None
            return None
    
    return _redis_client


class SessionStore:
    """Redis-backed session storage with automatic TTL.
    
    Stores session data (student context, class context, etc.) with
    automatic expiration to prevent memory leaks.
    
    Example:
        >>> store = SessionStore(ttl_days=7)
        >>> store.set("session_123", {"student": "Aisha", "class_id": "4B"})
        >>> data = store.get("session_123")
        >>> print(data["student"])  # "Aisha"
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        ttl_days: int = 7,
        key_prefix: str = "session:"
    ):
        """Initialize session store.
        
        Args:
            redis_client: Redis client (creates new if None)
            ttl_days: Time-to-live in days for sessions
            key_prefix: Prefix for session keys
        """
        self.redis = redis_client or get_redis_client()
        self.ttl = timedelta(days=ttl_days)
        self.key_prefix = key_prefix
        
        logger.info(f"SessionStore initialized with {ttl_days} day TTL")
    
    def _make_key(self, session_id: str) -> str:
        """Create full Redis key with prefix."""
        return f"{self.key_prefix}{session_id}"
    
    def get(self, session_id: str) -> Dict[str, Any]:
        """Get session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dict (empty if not found)
        """
        try:
            key = self._make_key(session_id)
            data = self.redis.get(key)
            
            if data:
                logger.debug(f"Session retrieved: {session_id}")
                return json.loads(data)
            else:
                logger.debug(f"Session not found: {session_id}")
                return {}
        
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}", exc_info=True)
            return {}
    
    def set(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Set session data with TTL.
        
        Args:
            session_id: Session identifier
            data: Session data dict
            
        Returns:
            True if successful
        """
        try:
            key = self._make_key(session_id)
            serialized = json.dumps(data, default=str)
            
            self.redis.setex(
                key,
                self.ttl,
                serialized
            )
            
            logger.debug(f"Session saved: {session_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}", exc_info=True)
            return False
    
    def delete(self, session_id: str) -> bool:
        """Delete session data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            key = self._make_key(session_id)
            deleted = self.redis.delete(key)
            
            if deleted:
                logger.debug(f"Session deleted: {session_id}")
                return True
            else:
                logger.debug(f"Session not found for deletion: {session_id}")
                return False
        
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
            return False
    
    def exists(self, session_id: str) -> bool:
        """Check if session exists.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session exists
        """
        try:
            key = self._make_key(session_id)
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Error checking session {session_id}: {e}", exc_info=True)
            return False
    
    def extend_ttl(self, session_id: str) -> bool:
        """Extend session TTL to full duration.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            key = self._make_key(session_id)
            return bool(self.redis.expire(key, self.ttl))
        except Exception as e:
            logger.error(f"Error extending TTL for {session_id}: {e}", exc_info=True)
            return False


class CacheManager:
    """Redis-backed cache for expensive operations.
    
    Caches analytics results, LLM responses, and other expensive computations
    with configurable TTL.
    
    Example:
        >>> cache = CacheManager(ttl_hours=1)
        >>> cache.set("student_stats:Aisha", {"sessions": 21, "avg_score": 64.7})
        >>> stats = cache.get("student_stats:Aisha")
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        ttl_hours: int = 1,
        key_prefix: str = "cache:"
    ):
        """Initialize cache manager.
        
        Args:
            redis_client: Redis client (creates new if None)
            ttl_hours: Time-to-live in hours for cached data
            key_prefix: Prefix for cache keys
        """
        self.redis = redis_client or get_redis_client()
        self.ttl = timedelta(hours=ttl_hours)
        self.key_prefix = key_prefix
        
        logger.info(f"CacheManager initialized with {ttl_hours} hour TTL")
    
    def _make_key(self, key: str) -> str:
        """Create full Redis key with prefix."""
        return f"{self.key_prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            redis_key = self._make_key(key)
            data = self.redis.get(redis_key)
            
            if data:
                logger.debug(f"Cache hit: {key}")
                return json.loads(data)
            else:
                logger.debug(f"Cache miss: {key}")
                return None
        
        except Exception as e:
            logger.error(f"Error retrieving cache {key}: {e}", exc_info=True)
            return None
    
    def set(self, key: str, value: Any, ttl_hours: Optional[int] = None) -> bool:
        """Set cached value with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl_hours: Override default TTL (optional)
            
        Returns:
            True if successful
        """
        try:
            redis_key = self._make_key(key)
            serialized = json.dumps(value, default=str)
            
            ttl = timedelta(hours=ttl_hours) if ttl_hours else self.ttl
            
            self.redis.setex(
                redis_key,
                ttl,
                serialized
            )
            
            logger.debug(f"Cache set: {key} (TTL: {ttl})")
            return True
        
        except Exception as e:
            logger.error(f"Error setting cache {key}: {e}", exc_info=True)
            return False
    
    def delete(self, key: str) -> bool:
        """Delete cached value.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        try:
            redis_key = self._make_key(key)
            deleted = self.redis.delete(redis_key)
            logger.debug(f"Cache deleted: {key}")
            return bool(deleted)
        except Exception as e:
            logger.error(f"Error deleting cache {key}: {e}", exc_info=True)
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.
        
        Args:
            pattern: Redis pattern (e.g., "student_stats:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            redis_pattern = self._make_key(pattern)
            keys = self.redis.keys(redis_pattern)
            
            if keys:
                deleted = self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} cache entries matching: {pattern}")
                return deleted
            
            return 0
        
        except Exception as e:
            logger.error(f"Error clearing cache pattern {pattern}: {e}", exc_info=True)
            return 0


def cached(ttl_hours: int = 1, key_prefix: str = ""):
    """Decorator for caching function results in Redis.
    
    Args:
        ttl_hours: Cache TTL in hours
        key_prefix: Prefix for cache keys
        
    Example:
        >>> @cached(ttl_hours=2, key_prefix="student_stats")
        >>> def get_student_stats(name: str):
        ...     # Expensive computation
        ...     return {"sessions": 21}
    """
    cache = CacheManager(ttl_hours=ttl_hours)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            # Hash for consistent key length
            cache_key = hashlib.md5(
                ":".join(key_parts).encode()
            ).hexdigest()
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Using cached result for {func.__name__}")
                return cached_value
            
            # Compute and cache
            logger.debug(f"Computing fresh result for {func.__name__}")
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl_hours=ttl_hours)
            
            return result
        
        return wrapper
    return decorator

