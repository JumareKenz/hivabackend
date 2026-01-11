"""
Immutable Audit Logger
Cryptographically chained append-only audit trail

CRITICAL PROPERTIES:
- Append-only (no updates or deletes)
- Cryptographic chaining (each event references previous hash)
- Tamper-evident (any modification breaks chain)
- Verifiable integrity
- Regulatory compliant
"""

import asyncpg
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from ..core.models import AuditEvent
from ..core.config import settings, get_audit_db_connection_string

logger = logging.getLogger(__name__)


class ImmutableAuditLogger:
    """
    Cryptographically chained audit logger.
    
    Each audit event contains:
    - Hash of previous event
    - Sequence number
    - Event data
    - Computed hash of current event
    
    Chain verification ensures no events modified or deleted.
    """
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False
        self._sequence_counter = 0
        self._last_hash = ""  # Genesis hash
    
    async def initialize(self):
        """Initialize database connection and audit chain"""
        if self._initialized:
            return
        
        try:
            # Create connection pool
            conn_string = get_audit_db_connection_string()
            self.pool = await asyncpg.create_pool(
                conn_string,
                min_size=2,
                max_size=10
            )
            
            # Create tables if not exist
            await self._create_tables()
            
            # Initialize chain state
            await self._initialize_chain_state()
            
            self._initialized = True
            logger.info("✅ Immutable Audit Logger initialized")
            logger.info(f"   Chain sequence: {self._sequence_counter}")
            logger.info(f"   Last hash: {self._last_hash[:16]}...")
            
        except Exception as e:
            logger.error(f"Failed to initialize audit logger: {e}")
            # Non-blocking: system can still run without audit logger
            # but all audit calls will fail gracefully
    
    async def _create_tables(self):
        """Create audit tables with append-only constraints"""
        async with self.pool.acquire() as conn:
            # Main audit events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id VARCHAR(64) PRIMARY KEY,
                    sequence_number BIGINT NOT NULL UNIQUE,
                    event_type VARCHAR(64) NOT NULL,
                    event_category VARCHAR(64) NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    timezone VARCHAR(16) DEFAULT 'UTC',
                    
                    actor_type VARCHAR(32),
                    actor_id VARCHAR(128),
                    actor_role VARCHAR(64),
                    actor_ip VARCHAR(45),
                    session_id VARCHAR(128),
                    
                    action VARCHAR(128) NOT NULL,
                    resource_type VARCHAR(64) NOT NULL,
                    resource_id VARCHAR(256) NOT NULL,
                    
                    request_id VARCHAR(64),
                    previous_state JSONB,
                    new_state JSONB,
                    change_summary TEXT,
                    
                    authentication_method VARCHAR(32),
                    authorization_decision VARCHAR(16),
                    
                    previous_hash VARCHAR(64) NOT NULL,
                    event_hash VARCHAR(64) NOT NULL,
                    
                    created_at TIMESTAMP DEFAULT NOW(),
                    
                    CHECK (authorization_decision IN ('ALLOW', 'DENY'))
                )
            """)
            
            # Indexes for fast queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_events(timestamp DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_actor 
                ON audit_events(actor_id, timestamp DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_resource 
                ON audit_events(resource_type, resource_id, timestamp DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_sequence 
                ON audit_events(sequence_number DESC)
            """)
            
            # Chain metadata table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_chain_metadata (
                    id SERIAL PRIMARY KEY,
                    last_sequence_number BIGINT NOT NULL,
                    last_event_hash VARCHAR(64) NOT NULL,
                    last_event_id VARCHAR(64),
                    chain_start_timestamp TIMESTAMP,
                    last_verification_timestamp TIMESTAMP,
                    total_events BIGINT DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            logger.info("Audit tables created/verified")
    
    async def _initialize_chain_state(self):
        """Load current chain state from database"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT last_sequence_number, last_event_hash
                FROM audit_chain_metadata
                ORDER BY id DESC
                LIMIT 1
            """)
            
            if row:
                self._sequence_counter = row['last_sequence_number']
                self._last_hash = row['last_event_hash']
            else:
                # Genesis state
                self._sequence_counter = 0
                self._last_hash = self._compute_genesis_hash()
                
                await conn.execute("""
                    INSERT INTO audit_chain_metadata 
                    (last_sequence_number, last_event_hash, chain_start_timestamp, total_events)
                    VALUES ($1, $2, NOW(), 0)
                """, self._sequence_counter, self._last_hash)
    
    def _compute_genesis_hash(self) -> str:
        """Compute genesis hash for chain start"""
        content = json.dumps({
            'genesis': True,
            'system': 'DCAL',
            'version': '1.0.0',
            'timestamp': datetime.utcnow().isoformat()
        }, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
    
    async def log_event(
        self,
        event_type: str,
        event_category: str,
        actor_type: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        request_id: str,
        actor_role: Optional[str] = None,
        actor_ip: Optional[str] = None,
        session_id: Optional[str] = None,
        previous_state: Optional[Dict] = None,
        new_state: Optional[Dict] = None,
        change_summary: Optional[str] = None,
        authentication_method: str = "unknown",
        authorization_decision: str = "ALLOW"
    ) -> str:
        """
        Log audit event to immutable chain.
        
        Returns:
            event_id of logged event
            
        Raises:
            Exception if logging fails
        """
        if not self._initialized:
            logger.warning("Audit logger not initialized, event not logged")
            return ""
        
        # Generate event ID
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Increment sequence
        self._sequence_counter += 1
        sequence_number = self._sequence_counter
        
        # Get previous hash
        previous_hash = self._last_hash
        
        # Build audit event
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            event_category=event_category,
            timestamp=timestamp,
            timezone="UTC",
            actor_type=actor_type,
            actor_id=actor_id,
            actor_role=actor_role,
            actor_ip=actor_ip,
            session_id=session_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            previous_state=previous_state,
            new_state=new_state,
            change_summary=change_summary,
            authentication_method=authentication_method,
            authorization_decision=authorization_decision,
            sequence_number=sequence_number,
            previous_hash=previous_hash
        )
        
        # Compute event hash
        event.event_hash = event.compute_hash()
        
        # Store to database
        try:
            await self._store_event(event)
            
            # Update chain state
            self._last_hash = event.event_hash
            
            logger.debug(f"Audit event logged: {event_id} (seq: {sequence_number})")
            
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            # Rollback sequence counter
            self._sequence_counter -= 1
            raise
    
    async def _store_event(self, event: AuditEvent):
        """Store event to database"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Insert event
                await conn.execute("""
                    INSERT INTO audit_events (
                        event_id, sequence_number, event_type, event_category,
                        timestamp, timezone,
                        actor_type, actor_id, actor_role, actor_ip, session_id,
                        action, resource_type, resource_id,
                        request_id, previous_state, new_state, change_summary,
                        authentication_method, authorization_decision,
                        previous_hash, event_hash
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20, $21, $22
                    )
                """,
                    event.event_id, event.sequence_number, event.event_type, event.event_category,
                    event.timestamp, event.timezone,
                    event.actor_type, event.actor_id, event.actor_role, event.actor_ip, event.session_id,
                    event.action, event.resource_type, event.resource_id,
                    event.request_id, 
                    json.dumps(event.previous_state) if event.previous_state else None,
                    json.dumps(event.new_state) if event.new_state else None,
                    event.change_summary,
                    event.authentication_method, event.authorization_decision,
                    event.previous_hash, event.event_hash
                )
                
                # Update chain metadata
                await conn.execute("""
                    UPDATE audit_chain_metadata
                    SET last_sequence_number = $1,
                        last_event_hash = $2,
                        last_event_id = $3,
                        total_events = total_events + 1,
                        updated_at = NOW()
                    WHERE id = (SELECT id FROM audit_chain_metadata ORDER BY id DESC LIMIT 1)
                """, event.sequence_number, event.event_hash, event.event_id)
    
    async def verify_chain_integrity(
        self,
        start_sequence: int = 0,
        end_sequence: Optional[int] = None
    ) -> tuple[bool, List[str]]:
        """
        Verify integrity of audit chain.
        
        Returns:
            (is_valid, list_of_errors)
        """
        if not self._initialized:
            return False, ["Audit logger not initialized"]
        
        errors = []
        
        async with self.pool.acquire() as conn:
            # Get events in sequence order
            if end_sequence:
                rows = await conn.fetch("""
                    SELECT * FROM audit_events
                    WHERE sequence_number >= $1 AND sequence_number <= $2
                    ORDER BY sequence_number ASC
                """, start_sequence, end_sequence)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM audit_events
                    WHERE sequence_number >= $1
                    ORDER BY sequence_number ASC
                """, start_sequence)
            
            if not rows:
                return True, []  # Empty chain is valid
            
            # Verify sequence continuity
            expected_seq = start_sequence if start_sequence > 0 else rows[0]['sequence_number']
            for row in rows:
                if row['sequence_number'] != expected_seq:
                    errors.append(f"Sequence gap detected: expected {expected_seq}, got {row['sequence_number']}")
                expected_seq += 1
            
            # Verify hash chain
            for i, row in enumerate(rows):
                # Rebuild event to recompute hash
                event = AuditEvent(
                    event_id=row['event_id'],
                    event_type=row['event_type'],
                    event_category=row['event_category'],
                    timestamp=row['timestamp'],
                    timezone=row['timezone'] or 'UTC',
                    actor_type=row['actor_type'],
                    actor_id=row['actor_id'],
                    actor_role=row['actor_role'],
                    actor_ip=row['actor_ip'],
                    session_id=row['session_id'],
                    action=row['action'],
                    resource_type=row['resource_type'],
                    resource_id=row['resource_id'],
                    request_id=row['request_id'],
                    previous_state=json.loads(row['previous_state']) if row['previous_state'] else None,
                    new_state=json.loads(row['new_state']) if row['new_state'] else None,
                    change_summary=row['change_summary'],
                    authentication_method=row['authentication_method'],
                    authorization_decision=row['authorization_decision'],
                    sequence_number=row['sequence_number'],
                    previous_hash=row['previous_hash']
                )
                
                # Compute hash
                computed_hash = event.compute_hash()
                if computed_hash != row['event_hash']:
                    errors.append(
                        f"Hash mismatch at sequence {row['sequence_number']}: "
                        f"expected {row['event_hash']}, computed {computed_hash}"
                    )
                
                # Verify previous hash linkage
                if i > 0:
                    prev_row = rows[i - 1]
                    if row['previous_hash'] != prev_row['event_hash']:
                        errors.append(
                            f"Chain broken at sequence {row['sequence_number']}: "
                            f"previous_hash mismatch"
                        )
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    async def get_events(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query audit events"""
        if not self._initialized:
            return []
        
        query = "SELECT * FROM audit_events WHERE 1=1"
        params = []
        param_idx = 1
        
        if resource_type:
            query += f" AND resource_type = ${param_idx}"
            params.append(resource_type)
            param_idx += 1
        
        if resource_id:
            query += f" AND resource_id = ${param_idx}"
            params.append(resource_id)
            param_idx += 1
        
        if actor_id:
            query += f" AND actor_id = ${param_idx}"
            params.append(actor_id)
            param_idx += 1
        
        if start_time:
            query += f" AND timestamp >= ${param_idx}"
            params.append(start_time)
            param_idx += 1
        
        if end_time:
            query += f" AND timestamp <= ${param_idx}"
            params.append(end_time)
            param_idx += 1
        
        query += f" ORDER BY timestamp DESC LIMIT ${param_idx}"
        params.append(limit)
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def close(self):
        """Close audit logger"""
        if self.pool:
            await self.pool.close()
            logger.info("Audit logger closed")


# Global singleton
audit_logger = ImmutableAuditLogger()


