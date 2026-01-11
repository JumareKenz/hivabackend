"""
Claims Processing Orchestrator
Coordinates all DCAL components to process claims end-to-end

Processing Flow:
1. Receive claim (from Kafka or API)
2. Retrieve supplementary data (HIP database)
3. Evaluate rules (deterministic gate)
4. Run ML fraud detection (if enabled)
5. Synthesize decision
6. Log to immutable audit trail
7. Publish result (to Kafka or return)
"""

import logging
import uuid
from typing import Optional
from datetime import datetime

from .core.models import ClaimData, ClaimIntelligenceReport, MLEngineResult
from .core.config import settings
from .data.hip_service import hip_service
from .rule_engine.engine import rule_engine
from .decision_engine.synthesis import decision_engine
from .audit.audit_logger import audit_logger
from .events.kafka_producer import kafka_producer

logger = logging.getLogger(__name__)


class ClaimsProcessingOrchestrator:
    """
    Orchestrates end-to-end claim processing through DCAL pipeline.
    
    CRITICAL DESIGN PRINCIPLES:
    - Never blocks backend claim submission
    - Fire-and-forget from backend perspective
    - All failures logged, none are silent
    - Graceful degradation if components unavailable
    - Every decision audited immutably
    """
    
    def __init__(self):
        self._initialized = False
    
    async def initialize(self):
        """Initialize all components"""
        if self._initialized:
            return
        
        logger.info("🚀 Initializing DCAL Claims Processing Orchestrator...")
        
        try:
            # Initialize HIP database service (read-only)
            await hip_service.initialize()
            
            # Initialize rule engine
            await rule_engine.initialize()
            
            # Initialize audit logger
            await audit_logger.initialize()
            
            # Initialize Kafka producer (if enabled)
            if settings.KAFKA_BOOTSTRAP_SERVERS != "localhost:9092" or settings.ENABLE_DEGRADATION_MODE:
                try:
                    await kafka_producer.start()
                except Exception as e:
                    logger.warning(f"Kafka producer failed to start: {e}")
                    logger.warning("Continuing in degraded mode without Kafka")
            
            self._initialized = True
            logger.info("✅ DCAL Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise
    
    async def process_claim(
        self,
        claim_data: ClaimData,
        request_id: Optional[str] = None
    ) -> ClaimIntelligenceReport:
        """
        Process a single claim through the complete DCAL pipeline.
        
        Args:
            claim_data: Sanitized claim data
            request_id: Optional request tracking ID
            
        Returns:
            Complete claim intelligence report
            
        Raises:
            Exception if processing fails critically
        """
        if not self._initialized:
            await self.initialize()
        
        request_id = request_id or f"REQ-{uuid.uuid4().hex[:16]}"
        start_time = datetime.utcnow()
        
        logger.info(f"📋 Processing claim {claim_data.claim_id} (request: {request_id})")
        
        try:
            # ===================================================================
            # STEP 1: Retrieve Supplementary Data from HIP Database
            # ===================================================================
            policy_data = None
            provider_data = None
            member_history = None
            provider_history = None
            
            try:
                # Get provider data
                provider_data = await hip_service.get_provider_data(claim_data.provider_id)
                
                # Get provider history
                provider_history = await hip_service.get_provider_history(claim_data.provider_id, days=90)
                
                # Get member history (if we can reverse the hash - currently not implemented)
                # member_history = await hip_service.get_member_history(claim_data.member_id_hash, days=90)
                
                logger.debug(f"  ✓ Supplementary data retrieved")
                
            except Exception as e:
                logger.warning(f"  ⚠ Failed to retrieve supplementary data: {e}")
                # Continue processing - not critical
            
            # ===================================================================
            # STEP 2: Evaluate Deterministic Rules (Gate 1)
            # ===================================================================
            logger.info(f"  🔍 Evaluating rules for {claim_data.claim_id}")
            
            rule_result = await rule_engine.evaluate_claim(
                claim_data=claim_data,
                policy_data=policy_data,
                provider_data=provider_data,
                member_history=member_history,
                provider_history=provider_history
            )
            
            logger.info(
                f"  ✓ Rules evaluated: {rule_result.aggregate_outcome.value} "
                f"({rule_result.rules_passed} passed, {rule_result.rules_failed} failed, "
                f"{rule_result.rules_flagged} flagged)"
            )
            
            # Log rule evaluation to audit
            await self._audit_rule_evaluation(claim_data, rule_result, request_id)
            
            # ===================================================================
            # STEP 3: ML Fraud Detection (Gate 2) - OPTIONAL
            # ===================================================================
            ml_result = None
            
            if settings.ENABLE_ML_ENGINE:
                logger.info(f"  🤖 Running ML fraud detection for {claim_data.claim_id}")
                
                try:
                    from .ml_engine.engine import ml_engine
                    
                    # Initialize ML engine if needed
                    if not ml_engine._initialized:
                        await ml_engine.initialize()
                    
                    # Run ML analysis
                    ml_result = await ml_engine.analyze_claim(
                        claim_data, provider_history, member_history
                    )
                    
                    logger.info(
                        f"  ✓ ML analysis complete: "
                        f"risk={ml_result.combined_risk_score:.2%}, "
                        f"confidence={ml_result.combined_confidence:.2%}"
                    )
                    
                except Exception as e:
                    logger.error(f"  ✗ ML engine failed: {e}")
                    # Continue without ML - rules are sufficient for basic operation
            
            # ===================================================================
            # STEP 4: Synthesize Final Decision
            # ===================================================================
            logger.info(f"  🧠 Synthesizing decision for {claim_data.claim_id}")
            
            intelligence_report = await decision_engine.synthesize_decision(
                claim_data=claim_data,
                rule_result=rule_result,
                ml_result=ml_result
            )
            
            logger.info(
                f"  ✓ Decision: {intelligence_report.recommendation.value} "
                f"(confidence: {intelligence_report.confidence_score:.2%}, "
                f"risk: {intelligence_report.risk_score:.2%})"
            )
            
            # ===================================================================
            # STEP 5: Audit Final Decision
            # ===================================================================
            await self._audit_decision(intelligence_report, request_id)
            
            # ===================================================================
            # STEP 6: Publish Result to Kafka (if enabled)
            # ===================================================================
            if kafka_producer._initialized:
                try:
                    await kafka_producer.publish_analysis_result(intelligence_report)
                    logger.debug(f"  ✓ Result published to Kafka")
                except Exception as e:
                    logger.warning(f"  ⚠ Failed to publish to Kafka: {e}")
                    # Non-blocking - result still returned
            
            # ===================================================================
            # STEP 7: Return Result
            # ===================================================================
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"✅ Claim {claim_data.claim_id} processed successfully "
                f"in {processing_time:.2f}s"
            )
            
            return intelligence_report
            
        except Exception as e:
            logger.error(f"❌ Failed to process claim {claim_data.claim_id}: {e}")
            
            # Log failure to audit
            await self._audit_processing_failure(claim_data, request_id, str(e))
            
            raise
    
    async def _audit_rule_evaluation(self, claim_data: ClaimData, rule_result, request_id: str):
        """Log rule evaluation to audit trail"""
        try:
            await audit_logger.log_event(
                event_type="rule_evaluation",
                event_category="claims_processing",
                actor_type="system",
                actor_id="rule_engine",
                action="evaluate_rules",
                resource_type="claim",
                resource_id=claim_data.claim_id,
                request_id=request_id,
                new_state={
                    'aggregate_outcome': rule_result.aggregate_outcome.value,
                    'rules_evaluated': rule_result.rules_evaluated,
                    'rules_passed': rule_result.rules_passed,
                    'rules_failed': rule_result.rules_failed,
                    'rules_flagged': rule_result.rules_flagged,
                    'triggered_rules': [r.rule_id for r in rule_result.triggered_rules]
                },
                change_summary=f"Rules evaluated: {rule_result.aggregate_outcome.value}"
            )
        except Exception as e:
            logger.warning(f"Failed to audit rule evaluation: {e}")
    
    async def _audit_decision(self, report: ClaimIntelligenceReport, request_id: str):
        """Log final decision to audit trail"""
        try:
            await audit_logger.log_event(
                event_type="decision_synthesized",
                event_category="claims_processing",
                actor_type="system",
                actor_id="decision_engine",
                action="synthesize_decision",
                resource_type="claim",
                resource_id=report.claim_id,
                request_id=request_id,
                new_state={
                    'analysis_id': report.analysis_id,
                    'recommendation': report.recommendation.value,
                    'confidence_score': report.confidence_score,
                    'risk_score': report.risk_score,
                    'assigned_queue': report.assigned_queue.value if report.assigned_queue else None,
                    'priority': report.priority.value
                },
                change_summary=f"Decision: {report.recommendation.value}"
            )
        except Exception as e:
            logger.warning(f"Failed to audit decision: {e}")
    
    async def _audit_processing_failure(self, claim_data: ClaimData, request_id: str, error: str):
        """Log processing failure to audit trail"""
        try:
            await audit_logger.log_event(
                event_type="processing_failure",
                event_category="claims_processing",
                actor_type="system",
                actor_id="orchestrator",
                action="process_claim",
                resource_type="claim",
                resource_id=claim_data.claim_id,
                request_id=request_id,
                change_summary=f"Processing failed: {error}",
                authorization_decision="DENY"
            )
        except Exception as e:
            logger.warning(f"Failed to audit processing failure: {e}")
    
    async def shutdown(self):
        """Graceful shutdown of all components"""
        logger.info("Shutting down DCAL orchestrator...")
        
        if kafka_producer._initialized:
            await kafka_producer.stop()
        
        await hip_service.close()
        await audit_logger.close()
        
        logger.info("DCAL orchestrator shutdown complete")


# Global singleton
orchestrator = ClaimsProcessingOrchestrator()

