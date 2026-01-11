"""
DCAL Configuration Management
Loads and validates all system configuration from environment variables
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, List
from pathlib import Path
import os

class Settings(BaseSettings):
    """
    Dynamic Claims Automation Layer Configuration
    All settings loaded from environment variables
    """
    
    # =============================================================================
    # SERVICE CONFIGURATION
    # =============================================================================
    SERVICE_NAME: str = "dcal-ai-engine"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    DEBUG: bool = False
    
    # =============================================================================
    # HIP DATABASE (READ-ONLY ACCESS)
    # =============================================================================
    HIP_DB_TYPE: str = "mysql"
    HIP_DB_HOST: str = "claimify-api.hayokmedicare.ng"
    HIP_DB_PORT: int = 3306
    HIP_DB_NAME: str = "hip"
    HIP_DB_USER: str = "hipnanle"
    HIP_DB_PASSWORD: str = Field(..., description="HIP DB password (from env)")
    HIP_DB_READ_ONLY: bool = True
    HIP_DB_MIN_POOL_SIZE: int = 2
    HIP_DB_MAX_POOL_SIZE: int = 10
    
    # =============================================================================
    # KAFKA MESSAGE BROKER
    # =============================================================================
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"  # PLAINTEXT, SASL_SSL
    KAFKA_SASL_MECHANISM: Optional[str] = None
    KAFKA_SASL_USERNAME: Optional[str] = None
    KAFKA_SASL_PASSWORD: Optional[str] = None
    
    # Topics
    KAFKA_TOPIC_CLAIMS_SUBMITTED: str = "claims.submitted"
    KAFKA_TOPIC_CLAIMS_ANALYZED: str = "claims.analyzed"
    KAFKA_TOPIC_CLAIMS_REVIEWED: str = "claims.reviewed"
    KAFKA_TOPIC_CLAIMS_FEEDBACK: str = "claims.feedback"
    
    # Consumer Configuration
    KAFKA_GROUP_ID: str = "dcal-ai-processor"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_MAX_POLL_RECORDS: int = 100
    
    # =============================================================================
    # AUDIT DATABASE (IMMUTABLE LOGS)
    # =============================================================================
    AUDIT_DB_TYPE: str = "postgresql"
    AUDIT_DB_HOST: str = "localhost"
    AUDIT_DB_PORT: int = 5432
    AUDIT_DB_NAME: str = "dcal_audit"
    AUDIT_DB_USER: str = "dcal_audit"
    AUDIT_DB_PASSWORD: str = Field(default="changeme", description="Audit DB password")
    
    # =============================================================================
    # SECURITY & AUTHENTICATION
    # =============================================================================
    JWT_SECRET_KEY: str = Field(..., description="JWT signing key")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    MESSAGE_SIGNING_KEY: str = Field(..., description="HMAC signing key for messages")
    MESSAGE_SIGNING_ALGORITHM: str = "HS256"
    
    MTLS_ENABLED: bool = False
    MTLS_CA_CERT_PATH: Optional[Path] = None
    MTLS_CLIENT_CERT_PATH: Optional[Path] = None
    MTLS_CLIENT_KEY_PATH: Optional[Path] = None
    
    # =============================================================================
    # RULE ENGINE CONFIGURATION
    # =============================================================================
    RULE_ENGINE_VERSION: str = "1.0.0"
    RULE_STORE_PATH: Path = Field(default=Path("/app/configs/rules"))
    RULE_CACHE_ENABLED: bool = True
    RULE_CACHE_TTL_SECONDS: int = 3600
    RULE_EVALUATION_TIMEOUT_MS: int = 5000
    
    # =============================================================================
    # ML ENGINE CONFIGURATION
    # =============================================================================
    ML_MODELS_PATH: Path = Field(default=Path("/app/models"))
    ML_FEATURE_CACHE_ENABLED: bool = True
    ML_INFERENCE_TIMEOUT_MS: int = 500
    ML_BATCH_SIZE: int = 32
    
    # Model Versions
    ML_MODEL_COST_ANOMALY_VERSION: str = "1.0.0"
    ML_MODEL_BEHAVIORAL_FRAUD_VERSION: str = "1.0.0"
    ML_MODEL_PROVIDER_ABUSE_VERSION: str = "1.0.0"
    ML_MODEL_FREQUENCY_SPIKE_VERSION: str = "1.0.0"
    
    # Thresholds
    ML_AUTO_APPROVE_THRESHOLD: float = 0.30
    ML_MEDIUM_RISK_THRESHOLD: float = 0.50
    ML_HIGH_RISK_THRESHOLD: float = 0.70
    ML_MIN_CONFIDENCE_FOR_AUTO: float = 0.85
    
    # =============================================================================
    # DECISION ENGINE CONFIGURATION
    # =============================================================================
    DECISION_ENGINE_VERSION: str = "1.0.0"
    AUTO_APPROVE_MAX_AMOUNT: float = 1000000.00
    AUTO_DECLINE_ON_CRITICAL_RULE: bool = True
    FORCE_REVIEW_ON_LOW_CONFIDENCE: bool = True
    HIGH_RISK_THRESHOLD: float = 0.70
    
    # SLA Timers (hours)
    SLA_CRITICAL_HOURS: int = 4
    SLA_HIGH_HOURS: int = 12
    SLA_MEDIUM_HOURS: int = 48
    SLA_LOW_HOURS: int = 120
    
    # =============================================================================
    # ADMIN PORTAL CONFIGURATION
    # =============================================================================
    ADMIN_PORTAL_HOST: str = "0.0.0.0"
    ADMIN_PORTAL_PORT: int = 8300
    ADMIN_SESSION_TIMEOUT_MINUTES: int = 30
    ADMIN_MFA_REQUIRED: bool = True
    
    OIDC_ISSUER_URL: Optional[str] = None
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[str] = None
    
    # =============================================================================
    # MONITORING & OBSERVABILITY
    # =============================================================================
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090
    METRICS_EXPORT_INTERVAL_SECONDS: int = 15
    
    SIEM_ENABLED: bool = False
    SIEM_ENDPOINT: Optional[str] = None
    
    # =============================================================================
    # FEATURE FLAGS
    # =============================================================================
    ENABLE_ML_ENGINE: bool = True
    ENABLE_AUTO_APPROVE: bool = False  # Start conservative
    ENABLE_AUTO_DECLINE: bool = False
    ENABLE_DEGRADATION_MODE: bool = True
    ENABLE_CIRCUIT_BREAKERS: bool = True
    
    # =============================================================================
    # RATE LIMITING
    # =============================================================================
    RATE_LIMIT_CLAIMS_PER_SECOND: int = 1000
    RATE_LIMIT_BURST_SIZE: int = 5000
    
    # =============================================================================
    # FAILURE HANDLING
    # =============================================================================
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = 30
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BACKOFF_SECONDS: int = 2
    
    @field_validator('RULE_STORE_PATH', 'ML_MODELS_PATH', mode='before')
    @classmethod
    def resolve_paths(cls, v):
        """Resolve paths relative to project root if not absolute"""
        if isinstance(v, str):
            path = Path(v)
            if not path.is_absolute():
                # Resolve relative to project root
                project_root = Path(__file__).parent.parent.parent
                return project_root / path
            return path
        return v
    
    @field_validator('HIP_DB_PASSWORD', 'AUDIT_DB_PASSWORD', 'JWT_SECRET_KEY', 'MESSAGE_SIGNING_KEY', mode='after')
    @classmethod
    def check_secrets(cls, v, info):
        """Ensure secrets are set in production"""
        if v == "changeme" or v == "":
            import os
            env = os.getenv('ENVIRONMENT', 'development')
            if env == 'production':
                raise ValueError(f"{info.field_name} must be set in production")
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()


# Helper functions
def is_production() -> bool:
    """Check if running in production environment"""
    return settings.ENVIRONMENT == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return settings.ENVIRONMENT == "development"


def get_hip_db_connection_string() -> str:
    """Get HIP database connection string"""
    if settings.HIP_DB_TYPE == "mysql":
        return f"mysql+aiomysql://{settings.HIP_DB_USER}:{settings.HIP_DB_PASSWORD}@{settings.HIP_DB_HOST}:{settings.HIP_DB_PORT}/{settings.HIP_DB_NAME}"
    elif settings.HIP_DB_TYPE == "postgresql":
        return f"postgresql+asyncpg://{settings.HIP_DB_USER}:{settings.HIP_DB_PASSWORD}@{settings.HIP_DB_HOST}:{settings.HIP_DB_PORT}/{settings.HIP_DB_NAME}"
    else:
        raise ValueError(f"Unsupported database type: {settings.HIP_DB_TYPE}")


def get_audit_db_connection_string() -> str:
    """Get audit database connection string"""
    return f"postgresql+asyncpg://{settings.AUDIT_DB_USER}:{settings.AUDIT_DB_PASSWORD}@{settings.AUDIT_DB_HOST}:{settings.AUDIT_DB_PORT}/{settings.AUDIT_DB_NAME}"


