"""
Admin Review Portal - FastAPI Application
RBAC-enabled portal for human-in-the-loop claim review
"""

import logging
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager

from ..core.config import settings
from ..orchestrator import orchestrator
from .auth import verify_token, get_current_user, require_role
from .routes import claims, queues, decisions, audit

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting Admin Review Portal...")
    try:
        await orchestrator.initialize()
        logger.info("✅ Admin Review Portal started successfully")
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Admin Review Portal...")
        await orchestrator.shutdown()
        logger.info("✅ Admin Review Portal shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="DCAL Admin Review Portal",
    description="Human-in-the-loop claims review and decision management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - Production-grade: NEVER use * when Authorization headers are present
# Whitelist specific origins for security
allowed_origins = [
    "http://localhost:3000",      # Development frontend
    "http://localhost:3001",      # Alternative dev port
    "http://127.0.0.1:3000",      # Localhost alternative
    "https://admin.hiva.chat",    # Production frontend
    "https://api.hiva.chat",       # API itself (for internal calls)
]

# NEVER use * when allow_credentials=True and Authorization headers are used
# This is a security requirement - browsers block * with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Always specific origins, never *
    allow_credentials=True,         # Required for Authorization headers
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight for 1 hour
)

# Security
security = HTTPBearer()

# Explicit OPTIONS handler for all /api/* routes to ensure CORS preflight works
# This ensures OPTIONS requests are handled before authentication middleware
@app.options("/api/{path:path}")
async def options_handler(path: str):
    """
    Handle OPTIONS preflight requests for all /api/* routes.
    Returns proper CORS headers without requiring authentication.
    """
    from fastapi.responses import Response
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "http://localhost:3000",  # Will be overridden by CORS middleware
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
            "Vary": "Origin",
        }
    )

# Include routers
app.include_router(claims.router, prefix="/api/claims", tags=["Claims"])
app.include_router(queues.router, prefix="/api/queues", tags=["Queues"])
app.include_router(decisions.router, prefix="/api/decisions", tags=["Decisions"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])


@app.get("/")
async def root():
    """API root"""
    return {
        "service": "DCAL Admin Review Portal",
        "version": "1.0.0",
        "status": "operational"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "orchestrator_initialized": orchestrator._initialized,
        "timestamp": str(datetime.utcnow())
    }


@app.get("/api/info")
async def api_info():
    """API information"""
    return {
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "features": {
            "ml_engine": settings.ENABLE_ML_ENGINE,
            "auto_approve": settings.ENABLE_AUTO_APPROVE,
            "auto_decline": settings.ENABLE_AUTO_DECLINE
        },
        "endpoints": {
            "claims": "/api/claims",
            "queues": "/api/queues",
            "decisions": "/api/decisions",
            "audit": "/api/audit"
        }
    }

