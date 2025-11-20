# services/ai/app/rag/index.py
from sentence_transformers import SentenceTransformer
from chromadb import Client
from app.core.config import settings

# Load your embedding model (use config or default)
EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
embedding_model = SentenceTransformer(EMBEDDING_MODEL)

# Initialize vector database
vector_db = Client().get_or_create_collection("faq_collection")
