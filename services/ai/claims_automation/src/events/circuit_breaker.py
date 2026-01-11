"""
Circuit Breaker Pattern Implementation
Prevents cascading failures when downstream services are unavailable
"""

import asyncio
import time
import logging
from enum import Enum
from typing import Callable, Any, Awaitable

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Failing, rejecting calls
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Failure threshold exceeded, calls rejected
    - HALF_OPEN: Testing recovery, limited calls allowed
    
    Thresholds:
    - failure_threshold: Consecutive failures before opening
    - timeout_seconds: How long to stay OPEN before testing
    - half_open_max_calls: Max calls to test in HALF_OPEN state
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Returns:
            Result of function if successful, None if circuit open
            
        Raises:
            Exception from function if it fails
        """
        async with self._lock:
            # Check if we should transition states
            await self._check_state_transition()
            
            if self.state == CircuitState.OPEN:
                logger.warning("Circuit breaker OPEN - rejecting call")
                return None
            
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    logger.warning("Circuit breaker HALF_OPEN limit reached")
                    return None
                self.half_open_calls += 1
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _check_state_transition(self):
        """Check if circuit breaker should change state"""
        if self.state == CircuitState.OPEN:
            # Check if timeout expired
            if time.time() - self.last_failure_time >= self.timeout_seconds:
                logger.info("Circuit breaker transitioning OPEN -> HALF_OPEN")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.failure_count = 0
    
    async def _on_success(self):
        """Handle successful call"""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                # If enough successes in HALF_OPEN, close circuit
                if self.success_count >= self.half_open_max_calls:
                    logger.info("Circuit breaker transitioning HALF_OPEN -> CLOSED")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN reopens circuit
                logger.warning("Circuit breaker transitioning HALF_OPEN -> OPEN (failure during test)")
                self.state = CircuitState.OPEN
                self.success_count = 0
            
            elif self.state == CircuitState.CLOSED:
                # Check if threshold exceeded
                if self.failure_count >= self.failure_threshold:
                    logger.error(f"Circuit breaker transitioning CLOSED -> OPEN (failures: {self.failure_count})")
                    self.state = CircuitState.OPEN
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        logger.info("Circuit breaker manually reset to CLOSED")


