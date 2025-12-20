"""
HIVA AI - Main FastAPI Application
Powered by Groq API
"""
import os
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from .api.v1.ask import router as ask_router
from .api.v1.stream import router as stream_router
from .api.v1.branches import router as branches_router
from .core import config

# Admin Insights router (optional - requires authentication)
try:
    from .api.v1.admin import router as admin_router
    ADMIN_ROUTER_AVAILABLE = True
except ImportError:
    ADMIN_ROUTER_AVAILABLE = False
    print("⚠️  Admin router not available")

# Groq API configuration
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("HIVA AI (Groq API) starting...")
    
    # Initialize branch configurations
    try:
        from .services.branch_config import initialize_branches
        initialize_branches()
        print("Branch configurations loaded")
    except Exception as e:
        print(f"Branch config error: {e}")
    
    # Initialize admin database service (non-blocking with timeout)
    try:
        from .services.database_service import database_service
        # Initialize with timeout to prevent blocking startup
        try:
            await asyncio.wait_for(database_service.initialize(), timeout=10.0)
        except asyncio.TimeoutError:
            print("⚠️  Database initialization timed out (will retry on first query)")
        except Exception as e:
            print(f"⚠️  Database service initialization: {e}")
    except Exception as e:
        print(f"Database service import error: {e}")
    
    yield
    
    # Cleanup
    try:
        from .services.database_service import database_service
        await database_service.close()
    except Exception:
        pass
    
    print("HIVA AI shutting down...")


app = FastAPI(
    title=config.settings.SERVICE_NAME,
    description="HIVA AI powered by Groq API",
    version="3.0.0",
    lifespan=lifespan
)

# ==================== CORS ====================
allowed_origins = config.settings.ALLOWED_ORIGINS + [
    "http://localhost:3000", "http://localhost:3001", "https://hiva-two.vercel.app",
    "http://localhost:5173", "http://localhost:8080", "http://127.0.0.1:3000",
    "http://127.0.0.1:5173", "https://ai.hiva.chat",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ROUTERS ====================
app.include_router(ask_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(branches_router, prefix="/api/v1")

# Admin Insights Router (Chat with Data)
if ADMIN_ROUTER_AVAILABLE:
    app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
    print("✅ Admin Insights API enabled")

# Admin Test Router (No Database Required - for local testing)
try:
    from .api.v1 import admin_test
    app.include_router(admin_test.router, prefix="/api/v1", tags=["Admin Test"])
    print("✅ Admin Test API enabled (no database required)")
except Exception as e:
    print(f"⚠️  Admin Test API not available: {e}")

# ==================== FRONTEND ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "rag")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path) if os.path.exists(index_path) else {"message": "HIVA 14B is live"}

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "model": config.settings.LLM_MODEL,
        "backend": "Groq API",
        "endpoint": GROQ_BASE_URL,
        "available_models": ["groq/compound", "groq/compound-mini", "openai/gpt-oss-20b"]
    }