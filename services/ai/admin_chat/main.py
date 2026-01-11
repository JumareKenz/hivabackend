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
from app.services.schema_mapper import schema_mapper
from app.services.domain_router import domain_router
from app.api.v1 import admin

# Import Vanna service (optional)
try:
    from app.services.vanna_service import vanna_service
    VANNA_AVAILABLE = True
except ImportError:
    VANNA_AVAILABLE = False
    vanna_service = None


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
        
        # Initialize schema mapper for intelligent domain routing
        print("🗺️  Initializing schema mapper...")
        try:
            await schema_mapper.initialize()
            print("✅ Schema mapper initialized")
        except Exception as e:
            print(f"⚠️  Schema mapper initialization error: {e}")
        
        # Initialize domain router
        print("🔄 Initializing domain router...")
        try:
            await domain_router.initialize()
            print("✅ Domain router initialized")
        except Exception as e:
            print(f"⚠️  Domain router initialization error: {e}")
        
        # Initialize Vanna AI if enabled
        if settings.USE_VANNA_AI and VANNA_AVAILABLE:
            print("🤖 Initializing Vanna AI...")
            try:
                vanna_initialized = await vanna_service.initialize()
                if vanna_initialized:
                    print("✅ Vanna AI initialized successfully")
                else:
                    print("⚠️  Vanna AI initialization failed, will use legacy SQL generator")
            except Exception as e:
                print(f"⚠️  Vanna AI initialization error: {e}, will use legacy SQL generator")
        elif settings.USE_VANNA_AI:
            print("⚠️  Vanna AI not available (package not installed), will use legacy SQL generator")
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
    vanna_enabled = settings.USE_VANNA_AI and VANNA_AVAILABLE and (
        vanna_service.is_available() if vanna_service else False
    )
    return {
        "service": "Hiva Admin Chat API",
        "version": "1.0.0",
        "status": "running",
        "database_available": database_service.pool is not None,
        "vanna_ai_enabled": vanna_enabled
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




