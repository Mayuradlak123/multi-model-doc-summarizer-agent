import pybreaker
from .logger import logger

# --- Specialized Fallbacks ---
def llm_fallback(*args, **kwargs):
    logger.error("🛡️ Circuit Breaker: Groq API Fallback executed.")
    class MockContent:
        def __init__(self, text):
            self.text = text
            self.content = text
    return MockContent("The Groq AI service is currently unavailable. Running in fallback mode.")

def chroma_fallback(*args, **kwargs):
    logger.error("🛡️ Circuit Breaker: ChromaDB Fallback executed.")
    return None

def neo4j_fallback(*args, **kwargs):
    logger.error("🛡️ Circuit Breaker: Neo4j Fallback executed.")
    return None

def redis_fallback(*args, **kwargs):
    logger.error("🛡️ Circuit Breaker: Redis Queue Fallback executed.")
    return None

# --- Custom Listener for Observability ---
class SeniorCircuitListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        if new_state == pybreaker.STATE_OPEN:
            logger.critical(f"🚨 Circuit {cb.name} TRIP! State -> OPEN. Recovery timeout starting.")
        elif new_state == pybreaker.STATE_HALF_OPEN:
            logger.info(f"🔄 Circuit {cb.name}: Timeout expired. Moving to HALF-OPEN trial.")
        elif new_state == pybreaker.STATE_CLOSED:
            logger.info(f"🟢 Circuit {cb.name} is now CLOSED. Full Recovery.")

# --- Initialize Breakers ---
llm_breaker = pybreaker.CircuitBreaker(
    fail_max=3, 
    reset_timeout=30, 
    listeners=[SeniorCircuitListener()]
)
llm_breaker.name = "GroqAPI"

chroma_breaker = pybreaker.CircuitBreaker(
    fail_max=3, 
    reset_timeout=60, 
    listeners=[SeniorCircuitListener()]
)
chroma_breaker.name = "ChromaDB"

neo4j_breaker = pybreaker.CircuitBreaker(
    fail_max=3, 
    reset_timeout=30, 
    listeners=[SeniorCircuitListener()]
)
neo4j_breaker.name = "Neo4j"

redis_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    listeners=[SeniorCircuitListener()]
)
redis_breaker.name = "RedisQueue"

# Wrapper to handle fallbacks
def with_breaker(breaker, fallback_func):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return breaker.call(func, *args, **kwargs)
            except pybreaker.CircuitBreakerError:
                return fallback_func(*args, **kwargs)
        return wrapper
    return decorator
