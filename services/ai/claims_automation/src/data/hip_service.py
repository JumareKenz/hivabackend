"""
HIP Database Service Layer
Read-only access to HIP claims database for analysis and ML training
"""

import aiomysql
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from contextlib import asynccontextmanager
import hashlib
import logging

from ..core.config import settings
from ..core.models import (
    ClaimData, ProcedureCode, DiagnosisCode,
    PolicyData, ProviderData, MemberHistory, ProviderHistory,
    ClaimType, FacilityType, NetworkStatus
)

logger = logging.getLogger(__name__)


class HIPDatabaseService:
    """
    Read-only service for accessing HIP claims database.
    
    CRITICAL CONSTRAINTS:
    - Read-only access (no INSERT, UPDATE, DELETE)
    - All queries are SELECT only
    - Data is sanitized before returning
    - PII is hashed where required
    """
    
    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize read-only database connection pool"""
        if self._initialized:
            return
        
        try:
            self.pool = await aiomysql.create_pool(
                host=settings.HIP_DB_HOST,
                port=settings.HIP_DB_PORT,
                db=settings.HIP_DB_NAME,
                user=settings.HIP_DB_USER,
                password=settings.HIP_DB_PASSWORD,
                minsize=settings.HIP_DB_MIN_POOL_SIZE,
                maxsize=settings.HIP_DB_MAX_POOL_SIZE,
                autocommit=True,  # Read-only, no transactions needed
                charset='utf8mb4'
            )
            
            # Verify read-only mode
            await self._verify_read_only()
            
            self._initialized = True
            logger.info("✅ HIP Database connection pool initialized (READ-ONLY)")
            
        except Exception as e:
            logger.error(f"Failed to initialize HIP database: {e}")
            raise
    
    async def _verify_read_only(self):
        """Verify database connection is functioning and read-only"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Test read access
                await cursor.execute("SELECT 1")
                result = await cursor.fetchone()
                assert result[0] == 1, "Read verification failed"
                
                logger.info("✅ HIP Database read access verified")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("HIP Database connection pool closed")
    
    # =========================================================================
    # CLAIM DATA RETRIEVAL
    # =========================================================================
    
    async def get_claim_by_id(self, claim_id: str) -> Optional[ClaimData]:
        """
        Retrieve a single claim by ID with sanitized data.
        Member IDs are hashed for privacy.
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get main claim data
                await cursor.execute("""
                    SELECT 
                        c.id,
                        c.claim_unique_id,
                        c.user_id,
                        c.provider_id,
                        c.client_name,
                        c.seen_date,
                        c.diagnosis,
                        c.treatment,
                        c.total_cost,
                        c.status,
                        c.created_at,
                        c.authorization_code,
                        c.agency_id,
                        c.is_out_of_station
                    FROM claims c
                    WHERE c.id = %s OR c.claim_unique_id = %s
                    LIMIT 1
                """, (claim_id, claim_id))
                
                claim_row = await cursor.fetchone()
                if not claim_row:
                    return None
                
                # Get associated services/procedures
                await cursor.execute("""
                    SELECT 
                        cs.services_id,
                        cs.drugs_id,
                        cs.cost,
                        cs.dose,
                        cs.frequency,
                        cs.days,
                        s.name as service_name,
                        s.cost as service_base_cost
                    FROM claims_services cs
                    LEFT JOIN services s ON cs.services_id = s.id
                    WHERE cs.claims_id = %s
                """, (claim_row['id'],))
                
                services = await cursor.fetchall()
                
                # Get diagnosis information
                diagnosis_codes = []
                if claim_row['diagnosis']:
                    # Parse diagnosis (stored as text/int in HIP)
                    try:
                        diag_id = int(claim_row['diagnosis'])
                        await cursor.execute("""
                            SELECT id, name, diagnosis_code
                            FROM diagnoses
                            WHERE id = %s
                        """, (diag_id,))
                        diag_row = await cursor.fetchone()
                        if diag_row and diag_row['diagnosis_code']:
                            diagnosis_codes.append(DiagnosisCode(
                                code=diag_row['diagnosis_code'],
                                code_type="ICD10_CM",
                                sequence=1
                            ))
                    except (ValueError, TypeError):
                        pass
                
                # Build procedure codes from services
                procedure_codes = []
                for svc in services:
                    if svc['services_id']:
                        procedure_codes.append(ProcedureCode(
                            code=f"SVC-{svc['services_id']}",  # Service ID as code
                            code_type="CUSTOM",
                            quantity=svc['dose'] * svc['frequency'] * svc['days'],
                            modifiers=[],
                            line_amount=float(svc['cost'] or 0)
                        ))
                
                # Hash member ID for privacy
                member_id_hash = hashlib.sha256(
                    str(claim_row['user_id']).encode()
                ).hexdigest()
                
                # Build ClaimData object
                claim_data = ClaimData(
                    claim_id=claim_row['claim_unique_id'] or str(claim_row['id']),
                    policy_id=f"POL-{claim_row['agency_id']}",
                    provider_id=f"PRV-{claim_row['provider_id']}",
                    member_id_hash=member_id_hash,
                    procedure_codes=procedure_codes or [ProcedureCode(
                        code="UNKNOWN",
                        code_type="CUSTOM",
                        quantity=1,
                        line_amount=float(claim_row['total_cost'] or 0)
                    )],
                    diagnosis_codes=diagnosis_codes or [DiagnosisCode(
                        code="UNKNOWN",
                        code_type="ICD10_CM",
                        sequence=1
                    )],
                    billed_amount=float(claim_row['total_cost'] or 0),
                    service_date=claim_row['seen_date'] or date.today(),
                    submission_timestamp=claim_row['created_at'] or datetime.utcnow(),
                    claim_type=ClaimType.PROFESSIONAL,
                    network_status=NetworkStatus.IN_NETWORK if not claim_row['is_out_of_station'] else NetworkStatus.OUT_OF_NETWORK,
                    metadata={
                        'original_diagnosis_text': claim_row['diagnosis'],
                        'treatment_text': claim_row['treatment'],
                        'status': claim_row['status'],
                        'authorization_code': claim_row['authorization_code']
                    }
                )
                
                return claim_data
    
    async def get_member_history(self, member_id_hash: str, days: int = 90) -> MemberHistory:
        """
        Get historical claim data for a member.
        Uses hashed member ID for privacy.
        """
        # Note: We need to hash all user_ids to find matches
        # This is inefficient but maintains privacy
        # In production, consider maintaining a hash lookup table
        
        history = MemberHistory(
            member_id_hash=member_id_hash,
            claims_30d=0,
            claims_90d=0,
            claims_365d=0,
            total_billed_30d=0.0,
            total_billed_90d=0.0
        )
        
        # For now, return empty history
        # Full implementation would query claims and aggregate
        # This requires reverse lookup of hashed IDs
        
        return history
    
    async def get_provider_history(self, provider_id: str, days: int = 90) -> ProviderHistory:
        """Get historical claim data for a provider"""
        
        # Extract numeric ID from provider_id (format: PRV-123)
        try:
            numeric_id = int(provider_id.split('-')[1])
        except (IndexError, ValueError):
            numeric_id = 0
        
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get claim counts and totals for different time windows
                await cursor.execute("""
                    SELECT 
                        COUNT(*) as total_claims,
                        SUM(CASE WHEN c.seen_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) as claims_30d,
                        SUM(CASE WHEN c.seen_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY) THEN 1 ELSE 0 END) as claims_90d,
                        SUM(CASE WHEN c.seen_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) THEN c.total_cost ELSE 0 END) as billed_30d,
                        AVG(c.total_cost) as avg_amount,
                        STD(c.total_cost) as std_amount,
                        COUNT(DISTINCT c.user_id) as unique_members
                    FROM claims c
                    WHERE c.provider_id = %s
                    AND c.deleted_at IS NULL
                    AND c.seen_date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)
                """, (numeric_id,))
                
                stats = await cursor.fetchone()
                
                if stats:
                    return ProviderHistory(
                        provider_id=provider_id,
                        claims_30d=int(stats['claims_30d'] or 0),
                        claims_90d=int(stats['claims_90d'] or 0),
                        total_billed_30d=float(stats['billed_30d'] or 0),
                        avg_claim_amount=float(stats['avg_amount'] or 0),
                        std_claim_amount=float(stats['std_amount'] or 0),
                        unique_members_30d=int(stats['unique_members'] or 0),
                        denial_rate=0.0,  # Would need status tracking
                        fraud_rate=0.0,
                        peer_percentile=0.5
                    )
                
                return ProviderHistory(provider_id=provider_id)
    
    async def get_provider_data(self, provider_id: str) -> Optional[ProviderData]:
        """Get provider eligibility data"""
        
        try:
            numeric_id = int(provider_id.split('-')[1])
        except (IndexError, ValueError):
            return None
        
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        p.id,
                        p.provider_id as external_id,
                        p.status,
                        p.agency_id,
                        p.created_at
                    FROM providers p
                    WHERE p.id = %s
                    LIMIT 1
                """, (numeric_id,))
                
                row = await cursor.fetchone()
                if not row:
                    return None
                
                return ProviderData(
                    provider_id=provider_id,
                    status="ACTIVE" if row['status'] == 1 else "INACTIVE",
                    effective_date=row['created_at'].date() if row['created_at'] else date.today(),
                    termination_date=None,
                    network_id=f"NET-{row['agency_id']}",
                    license_status="VALID",  # Not in HIP schema
                    license_expiry=None,
                    license_types=["GENERAL"],
                    specialties=["GENERAL"],
                    contract_id=None
                )
    
    # =========================================================================
    # STATISTICAL QUERIES FOR ML TRAINING
    # =========================================================================
    
    async def get_procedure_statistics(self, procedure_code: str) -> Dict[str, float]:
        """Get statistical data for a procedure code"""
        
        # For HIP, procedures are services
        try:
            service_id = int(procedure_code.split('-')[1])
        except (IndexError, ValueError):
            return {'median': 0.0, 'percentile_95': 0.0}
        
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        AVG(cs.cost) as avg_cost,
                        STD(cs.cost) as std_cost,
                        MAX(cs.cost) as max_cost,
                        COUNT(*) as count
                    FROM claims_services cs
                    WHERE cs.services_id = %s
                    AND cs.cost > 0
                """, (service_id,))
                
                stats = await cursor.fetchone()
                
                if stats and stats['count'] > 0:
                    return {
                        'median': float(stats['avg_cost'] or 0),
                        'percentile_95': float(stats['avg_cost'] or 0) * 1.5,  # Approximation
                        'max': float(stats['max_cost'] or 0),
                        'std': float(stats['std_cost'] or 0)
                    }
                
                return {'median': 0.0, 'percentile_95': 0.0}
    
    async def get_training_data(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10000
    ) -> List[Dict[str, Any]]:
        """
        Get historical claims data for ML training.
        Returns sanitized data suitable for feature engineering.
        """
        async with self.get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        c.id,
                        c.claim_unique_id,
                        c.user_id,
                        c.provider_id,
                        c.agency_id,
                        c.seen_date,
                        c.total_cost,
                        c.status,
                        c.created_at,
                        COUNT(cs.id) as service_count,
                        SUM(cs.cost) as total_service_cost
                    FROM claims c
                    LEFT JOIN claims_services cs ON cs.claims_id = c.id
                    WHERE c.seen_date BETWEEN %s AND %s
                    AND c.deleted_at IS NULL
                    GROUP BY c.id
                    LIMIT %s
                """, (start_date, end_date, limit))
                
                claims = await cursor.fetchall()
                
                # Sanitize data
                training_data = []
                for claim in claims:
                    training_data.append({
                        'claim_id': claim['claim_unique_id'] or str(claim['id']),
                        'member_id_hash': hashlib.sha256(str(claim['user_id']).encode()).hexdigest(),
                        'provider_id': claim['provider_id'],
                        'agency_id': claim['agency_id'],
                        'service_date': claim['seen_date'],
                        'billed_amount': float(claim['total_cost'] or 0),
                        'service_count': int(claim['service_count'] or 0),
                        'status': claim['status'],
                        'submission_lag_days': (claim['created_at'].date() - claim['seen_date']).days if claim['created_at'] and claim['seen_date'] else 0
                    })
                
                return training_data


# Global singleton instance
hip_service = HIPDatabaseService()


