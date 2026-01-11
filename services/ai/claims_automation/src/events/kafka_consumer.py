"""
Kafka Consumer for Claims Events
Fire-and-forget semantics with circuit breakers
"""

import json
import asyncio
import hashlib
import hmac
import logging
from typing import Optional, Callable, Awaitable
from datetime import datetime

try:
    from aiokafka import AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("aiokafka not installed - Kafka features disabled")

from ..core.config import settings
from ..core.models import ClaimData
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class ClaimsKafkaConsumer:
    """
    Consumes claim events from Kafka with resilience:
    - Circuit breaker protection
    - Message validation
    - HMAC signature verification
    - Graceful degradation
    """
    
    def __init__(self, handler: Callable[[ClaimData], Awaitable[None]]):
        """
        Args:
            handler: Async function to process each claim
        """
        if not KAFKA_AVAILABLE:
            raise RuntimeError("aiokafka not installed")
        
        self.handler = handler
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            timeout_seconds=settings.CIRCUIT_BREAKER_TIMEOUT_SECONDS,
            half_open_max_calls=settings.CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS
        )
        self._running = False
    
    async def start(self):
        """Start consuming events"""
        if not KAFKA_AVAILABLE:
            logger.error("Kafka consumer cannot start - aiokafka not installed")
            return
        
        try:
            self.consumer = AIOKafkaConsumer(
                settings.KAFKA_TOPIC_CLAIMS_SUBMITTED,
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                group_id=settings.KAFKA_GROUP_ID,
                auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
                enable_auto_commit=False,  # Manual commit for safety
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                max_poll_records=settings.KAFKA_MAX_POLL_RECORDS
            )
            
            await self.consumer.start()
            self._running = True
            
            logger.info("✅ Kafka consumer started")
            logger.info(f"   Topic: {settings.KAFKA_TOPIC_CLAIMS_SUBMITTED}")
            logger.info(f"   Group: {settings.KAFKA_GROUP_ID}")
            
            # Start consumption loop
            await self._consume_loop()
            
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            raise
    
    async def _consume_loop(self):
        """Main consumption loop"""
        while self._running:
            try:
                # Get batch of messages
                messages = await self.consumer.getmany(timeout_ms=1000, max_records=100)
                
                for topic_partition, msgs in messages.items():
                    for msg in msgs:
                        try:
                            await self._process_message(msg)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            # Don't stop on individual message errors
                            continue
                    
                    # Commit offsets after processing batch
                    await self.consumer.commit()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consumption loop: {e}")
                await asyncio.sleep(5)  # Backoff
    
    async def _process_message(self, msg):
        """Process a single Kafka message"""
        
        # Circuit breaker check
        if not await self.circuit_breaker.call(self._process_claim, msg.value):
            logger.warning(f"Circuit breaker open - skipping message")
            return
    
    async def _process_claim(self, message_data: dict) -> bool:
        """
        Process claim message.
        Returns True on success, False on failure (for circuit breaker)
        """
        try:
            # Step 1: Validate message structure
            if not self._validate_message_structure(message_data):
                logger.error("Invalid message structure")
                return False
            
            # Step 2: Verify HMAC signature
            if not self._verify_signature(message_data):
                logger.error("HMAC signature verification failed")
                return False
            
            # Step 3: Extract claim data
            claim_data = self._deserialize_claim(message_data['payload'])
            if not claim_data:
                logger.error("Failed to deserialize claim data")
                return False
            
            # Step 4: Call handler
            await self.handler(claim_data)
            
            logger.info(f"Successfully processed claim: {claim_data.claim_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing claim: {e}")
            return False
    
    def _validate_message_structure(self, message: dict) -> bool:
        """Validate message has required fields"""
        required_fields = ['message_id', 'timestamp', 'payload', 'signature']
        return all(field in message for field in required_fields)
    
    def _verify_signature(self, message: dict) -> bool:
        """Verify HMAC signature of message"""
        try:
            # Extract signature
            received_sig = message.get('signature', '')
            
            # Compute expected signature
            payload_str = json.dumps(message['payload'], sort_keys=True)
            expected_sig = hmac.new(
                settings.MESSAGE_SIGNING_KEY.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Constant-time comparison
            return hmac.compare_digest(received_sig, expected_sig)
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def _deserialize_claim(self, payload: dict) -> Optional[ClaimData]:
        """Convert message payload to ClaimData object"""
        try:
            from ..core.models import ProcedureCode, DiagnosisCode, ClaimType, NetworkStatus
            from datetime import date
            
            # Parse procedures
            procedures = [
                ProcedureCode(
                    code=p['code'],
                    code_type=p['code_type'],
                    quantity=p.get('quantity', 1),
                    modifiers=p.get('modifiers', []),
                    line_amount=p.get('line_amount')
                )
                for p in payload.get('procedure_codes', [])
            ]
            
            # Parse diagnoses
            diagnoses = [
                DiagnosisCode(
                    code=d['code'],
                    code_type=d['code_type'],
                    sequence=d.get('sequence', 1)
                )
                for d in payload.get('diagnosis_codes', [])
            ]
            
            # Parse dates
            service_date = date.fromisoformat(payload['service_date']) if isinstance(payload['service_date'], str) else payload['service_date']
            service_date_end = date.fromisoformat(payload['service_date_end']) if payload.get('service_date_end') else None
            
            # Build ClaimData
            claim = ClaimData(
                claim_id=payload['claim_id'],
                policy_id=payload['policy_id'],
                provider_id=payload['provider_id'],
                member_id_hash=payload['member_id_hash'],
                procedure_codes=procedures,
                diagnosis_codes=diagnoses,
                billed_amount=float(payload['billed_amount']),
                service_date=service_date,
                service_date_end=service_date_end,
                claim_type=ClaimType(payload.get('claim_type', 'PROFESSIONAL')),
                network_status=NetworkStatus(payload.get('network_status', 'UNKNOWN')),
                metadata=payload.get('metadata', {})
            )
            
            return claim
            
        except Exception as e:
            logger.error(f"Failed to deserialize claim: {e}")
            return None
    
    async def stop(self):
        """Stop consuming"""
        self._running = False
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer stopped")


# Example usage function
async def create_claims_consumer(handler: Callable[[ClaimData], Awaitable[None]]) -> ClaimsKafkaConsumer:
    """
    Create and start a claims consumer.
    
    Args:
        handler: Async function to process each claim
        
    Returns:
        Started consumer instance
    """
    consumer = ClaimsKafkaConsumer(handler)
    await consumer.start()
    return consumer


