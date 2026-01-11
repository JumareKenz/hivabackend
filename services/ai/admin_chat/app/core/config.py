"""
Admin Chat Configuration
Separate from RAG chatbot - uses Groq API (same as users/providers)
"""
from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the admin_chat directory or parent
app_root = Path(__file__).parent.parent.parent.parent  # Go up to ai/ directory
env_path = app_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback: try current directory
    load_dotenv()


class AdminSettings(BaseSettings):
    """Admin Chat Service Configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "hiva-admin-chat"
    HOST: str = "0.0.0.0"  # Listen on all interfaces for external access
    PORT: int = 8001  # Different port from RAG chatbot (8000)
    API_BASE_URL: str = "https://api.hiva.chat"
    
    ALLOWED_ORIGINS: list = [
        "https://hiva.chat",
        "https://api.hiva.chat",
        "http://localhost:3000",
        "http://localhost:5173",
        "https://hiva-two.vercel.app",
    ]
    
    # RunPod GPU LLM Configuration (Primary - for admin/vanna LLM)
    RUNPOD_API_KEY: Optional[str] = None  # Set in .env file
    RUNPOD_BASE_URL: str = "https://6j0stkh7bjoio1-8000.proxy.runpod.net/v1"  # RunPod proxy endpoint
    LLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"  # Model on RunPod
    LLM_TIMEOUT: int = 300
    DEFAULT_NUM_PREDICT: int = 2000  # Higher for SQL generation
    TEMPERATURE: float = 0.1  # Lower for SQL accuracy
    
    # Groq API Configuration (Fallback - if RunPod is not available)
    GROQ_API_KEY: Optional[str] = None  # Set in .env file
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"  # Groq API endpoint
    
    # Admin Authentication
    ADMIN_API_KEY: Optional[str] = None  # Set in .env for admin authentication
    
    # Analytics Database Configuration (PHI Data - Read-Only)
    ANALYTICS_DB_TYPE: str = "mysql"  # postgresql or mysql
    ANALYTICS_DB_HOST: Optional[str] = "claimify-api.hayokmedicare.ng"  # Database host (without https:// or /adminer)
    ANALYTICS_DB_PORT: Optional[str] = "3306"  # MySQL default port
    ANALYTICS_DB_NAME: Optional[str] = None  # Database name (set in .env)
    ANALYTICS_DB_USER: Optional[str] = None  # Database username (set in .env)
    ANALYTICS_DB_PASSWORD: Optional[str] = None  # Database password (set in .env)
    
    # Conversation Management
    MAX_CONVERSATION_HISTORY: int = 10
    
    # MCP Migration Feature Flags
    # DISABLED: MCP mode is disabled to ensure Phase 4 validator runs
    # The validator is integrated into legacy mode and must be used for all queries
    USE_MCP_MODE: bool = False  # DISABLED - Legacy mode with validator is required
    MCP_GRADUAL_ROLLOUT: float = 0.0  # DISABLED - No MCP traffic
    MCP_FALLBACK_TO_LEGACY: bool = True  # DISABLED - MCP not in use
    
    # Vanna AI Feature Flags
    USE_VANNA_AI: bool = True  # Set to True to enable Vanna AI for SQL generation
    VANNA_FALLBACK_TO_LEGACY: bool = True  # Fallback to legacy SQL generator if Vanna fails
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from shared .env


settings = AdminSettings()


