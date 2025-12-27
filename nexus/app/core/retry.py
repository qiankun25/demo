import asyncio
import logging
import random
from typing import Type, Tuple, Callable, Any, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")

class RetryConfig:
    def __init__(
        self, 
        max_attempts: int = 3, 
        initial_delay: float = 1.0, 
        max_delay: float = 30.0, 
        exponential_base: float = 2.0,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retryable_exceptions = retryable_exceptions

def with_retry(config: RetryConfig = RetryConfig()):
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            delay = config.initial_delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    attempt += 1
                    if attempt >= config.max_attempts:
                        logger.error(f"Retry limit reached for {func.__name__}: {e}")
                        raise
                    
                    logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                    
                    delay = min(delay * config.exponential_base, config.max_delay)
                    # Add jitter
                    delay = delay * (1 + random.uniform(-0.1, 0.1))
        return wrapper
    return decorator
