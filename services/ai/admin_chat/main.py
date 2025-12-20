"""
Admin Chat Service - Main FastAPI Application
Natural language to SQL analytics for internal staff
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from app.core.config import settings
from app.services.database_service import database_service
from app.api.v1 import admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    print("🚀 Starting Admin Chat Service...")
    print(f"   Service: {settings.SERVICE_NAME}")
    print(f"   Host: {settings.HOST}")
    print(f"   Port: {settings.PORT}")
    
    # Initialize database connection
    print("📊 Initializing database connection...")
    await database_service.initialize()
    
    if database_service.pool:
        print("✅ Database connection pool initialized")
    else:
        print("⚠️  Database not configured - admin insights will be disabled")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Admin Chat Service...")
    await database_service.close()
    print("✅ Database connection pool closed")


# Create FastAPI app
app = FastAPI(
    title="Hiva Admin Chat API",
    description="Natural language to SQL analytics for internal staff",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Hiva Admin Chat API",
        "version": "1.0.0",
        "status": "running",
        "database_available": database_service.pool is not None
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database_available": database_service.pool is not None
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info",
        timeout_keep_alive=300,  # Keep connections alive for 5 minutes
        timeout_graceful_shutdown=30
    )




