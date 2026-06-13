import importlib
from .logger import logger
from .settings import settings
from .circuit_breaker import llm_breaker, chroma_breaker, neo4j_breaker, redis_breaker, with_breaker
from .postgres_config import postgres_manager

_chroma_client = None
_redis_client = None
_async_redis_client = None
_neo4j_manager = None

def __getattr__(name):
    global _chroma_client, _redis_client, _async_redis_client, _neo4j_manager
    
    if name == "chroma_client":
        if _chroma_client is None:
            from .chroma_config import chroma_client
            _chroma_client = chroma_client
        return _chroma_client
        
    if name == "redis_client":
        if _redis_client is None:
            from .redis_config import redis_client
            _redis_client = redis_client
        return _redis_client
        
    if name == "async_redis_client":
        if _async_redis_client is None:
            from .redis_config import async_redis_client
            _async_redis_client = async_redis_client
        return _async_redis_client
        
    if name == "neo4j_manager":
        if _neo4j_manager is None:
            from .neo4j_config import neo4j_manager
            _neo4j_manager = neo4j_manager
        return _neo4j_manager
        
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

def __dir__():
    return sorted(globals().keys() | {
        "chroma_client", "redis_client", "async_redis_client", "neo4j_manager"
    })
