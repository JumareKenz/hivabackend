# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from .api.v1.ask import router as ask_router
from .api.v1.stream import router as stream_router
from .api.v1.branches import router as branches_router
from .core import config
from .services.ollama_client import get_ollama_client, close_ollama_client
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Initialize Ollama client
    print("🚀 Initializing HIVA AI Assistant...")
    try:
        await get_ollama_client()
        print("✅ Ollama client initialized")
        
        # Warm up Ollama for faster first response
        from app.core.config import settings
        if settings.ENABLE_WARMUP:
            print("🔥 Warming up Ollama...")
            from app.services.performance_optimizer import PerformanceOptimizer
            await PerformanceOptimizer.warmup_ollama()
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize Ollama client: {e}")
    
    # Load branch configurations
    try:
        from .services.branch_config import initialize_branches
        initialize_branches()
    except Exception as e:
        print(f"⚠️  Could not initialize branch configs: {e}")
    
    yield
    
    # Shutdown: Close Ollama client
    print("🛑 Shutting down...")
    await close_ollama_client()
    print("✅ Cleanup complete")


app = FastAPI(
    title=config.settings.SERVICE_NAME,
    description="State-of-the-art AI assistant for insurance company with 9 branches",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend
allowed_origins = config.settings.ALLOWED_ORIGINS + [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.include_router(ask_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(branches_router, prefix="/api/v1")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "rag")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "HIVA AI Assistant API", "version": "2.0.0", "status": "running"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": config.settings.SERVICE_NAME}
