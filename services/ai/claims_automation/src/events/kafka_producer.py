"""
Kafka Producer for Claim Analysis Results
Publishes decision reports back to event bus
"""

import json
import hashlib
import hmac
import uuid
import logging
from typing import Optional
from datetime import datetime

try:
    from aiokafka import AIOKafkaProducer
    from aiokafka.errors import KafkaError
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("aiokafka not installed - Kafka features disabled")

from ..core.config import settings
from ..core.models import ClaimIntelligenceReport

logger = logging.getLogger(__name__)


class ClaimsKafkaProducer:
    """
    Publishes claim analysis results to Kafka.
    - HMAC message signing
    - Automatic retries
    - Message validation
    """
    
    def __init__(self):
        if not KAFKA_AVAILABLE:
            raise RuntimeError("aiokafka not installed")
        
        self.producer: Optional[AIOKafkaProducer] = None
        self._initialized = False
    
    async def start(self):
        """Start producer"""
        if not KAFKA_AVAILABLE:
            logger.error("Kafka producer cannot start - aiokafka not installed")
            return
        
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                compression_type='gzip',
                max_request_size=1048576,  # 1MB
                request_timeout_ms=30000,
                retries=3
            )
            
            await self.producer.start()
            self._initialized = True
            
            logger.info("✅ Kafka producer started")
            logger.info(f"   Bootstrap: {settings.KAFKA_BOOTSTRAP_SERVERS}")
            
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            raise
    
    async def publish_analysis_result(self, report: ClaimIntelligenceReport) -> bool:
        """
        Publish claim analysis result.
        
        Returns:
            True if published successfully, False otherwise
        """
        if not self._initialized:
            logger.error("Producer not initialized")
            return False
        
        try:
            # Build message
            message = self._build_message(report)
            
            # Send to Kafka
            await self.producer.send_and_wait(
                settings.KAFKA_TOPIC_CLAIMS_ANALYZED,
                value=message,
                key=report.claim_id.encode('utf-8')
            )
            
            logger.info(f"Published analysis for claim {report.claim_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish analysis: {e}")
            return False
    
    def _build_message(self, report: ClaimIntelligenceReport) -> dict:
        """Build signed message from report"""
        
        # Serialize report
        payload = {
            'analysis_id': report.analysis_id,
            'claim_id': report.claim_id,
            'timestamp': report.timestamp.isoformat(),
            'recommendation': report.recommendation.value,
            'confidence_score': report.confidence_score,
            'risk_score': report.risk_score,
            'assigned_queue': report.assigned_queue.value if report.assigned_queue else None,
            'priority': report.priority.value,
            'sla_hours': report.sla_hours,
            'primary_reasons': report.primary_reasons,
            'secondary_factors': report.secondary_factors,
            'risk_indicators': report.risk_indicators,
            'suggested_actions': report.suggested_actions,
            'rule_engine_details': report.rule_engine_details,
            'ml_engine_details': report.ml_engine_details
        }
        
        # Compute HMAC signature
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            settings.MESSAGE_SIGNING_KEY.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Build message envelope
        message = {
            'message_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'dcal-ai-engine',
            'event_type': 'claim.analyzed',
            'payload': payload,
            'signature': signature
        }
        
        return message
    
    async def stop(self):
        """Stop producer"""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")


# Global singleton
kafka_producer = ClaimsKafkaProducer()


