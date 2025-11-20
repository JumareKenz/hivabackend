# services/ai/app/rag/ingest.py
import os
import glob
import chromadb
from sentence_transformers import SentenceTransformer
from app.rag.utils import extract_text_from_pdf, extract_text_from_docx, chunk_text
from app.core.config import settings

# Calculate paths relative to this file
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_BASE_DIR, "db")
FAQ_DIR = os.path.join(_BASE_DIR, "faqs")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Import config for embedding model
EMBEDDING_MODEL = getattr(settings, "EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

def ingest_faqs(branch_id: str = None, clear_existing: bool = False):
    """
    Ingest FAQs into the vector database.
    
    Args:
        branch_id: Optional branch ID to filter files (e.g., "lagos", "abuja")
                   If None, processes all FAQs including branch-specific ones
        clear_existing: If True, clears the collection before ingesting
    """
    print(f"Loading embedding model: {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("✓ Model loaded")

    # Ensure directories exist
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(FAQ_DIR, exist_ok=True)
    
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection("faqs")

    if clear_existing:
        print("⚠️  Clearing existing collection...")
        # Delete and recreate collection
        client.delete_collection("faqs")
        collection = client.get_or_create_collection("faqs")
        print("✓ Collection cleared")

    # Determine which files to process
    if branch_id:
        # Process branch-specific files
        branch_patterns = [
            os.path.join(FAQ_DIR, "branches", branch_id, "*"),
            os.path.join(FAQ_DIR, f"*{branch_id}*"),
            os.path.join(FAQ_DIR, branch_id, "*"),
        ]
        files = []
        for pattern in branch_patterns:
            files.extend(glob.glob(pattern))
        files = list(set(files))  # Remove duplicates
        print(f"Processing {len(files)} files for branch: {branch_id}")
    else:
        # Process all files
        patterns = [
            os.path.join(FAQ_DIR, "*"),  # Root FAQ files
            os.path.join(FAQ_DIR, "branches", "*", "*"),  # Branch-specific files
            os.path.join(FAQ_DIR, "*", "*"),  # Any subdirectories
        ]
        files = []
        for pattern in patterns:
            files.extend(glob.glob(pattern))
        files = [f for f in set(files) if os.path.isfile(f)]  # Remove duplicates and directories
        print(f"Processing {len(files)} files (all branches)")

    if not files:
        print(f"⚠️  No files found in {FAQ_DIR}")
        print("📁 Expected structure:")
        print("   faqs/")
        print("   ├── general_faqs.pdf")
        print("   ├── branches/")
        print("   │   ├── lagos/")
        print("   │   │   ├── lagos_policies.pdf")
        print("   │   │   └── lagos_procedures.txt")
        print("   │   ├── abuja/")
        print("   │   │   └── abuja_faqs.pdf")
        print("   │   └── ... (other branches)")
        return

    total_chunks = 0
    for file in files:
        print(f"Processing: {os.path.basename(file)}")
        
        # Extract text
        if file.endswith(".pdf"):
            content = extract_text_from_pdf(file)
        elif file.endswith(".docx"):
            content = extract_text_from_docx(file)
        elif file.endswith((".txt", ".md")):
            with open(file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        else:
            print(f"  ⚠️  Skipping unsupported file type: {file}")
            continue

        if not content.strip():
            print(f"  ⚠️  No text extracted from {file}, skipping")
            continue

        # Determine branch from file path
        file_branch_id = None
        if "branches" in file:
            # Extract branch from path like: faqs/branches/lagos/file.pdf
            parts = file.split(os.sep)
            if "branches" in parts:
                branch_idx = parts.index("branches")
                if branch_idx + 1 < len(parts):
                    file_branch_id = parts[branch_idx + 1]
        elif branch_id:
            file_branch_id = branch_id

        # Chunk text
        chunks = chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
        
        # Add chunks with metadata
        for i, chunk in enumerate(chunks):
            doc_id = f"{os.path.basename(file)}_chunk_{i}"
            metadata = {
                "source_file": os.path.basename(file),
                "file_path": file,
            }
            if file_branch_id:
                metadata["branch_id"] = file_branch_id
            
            collection.add(
                documents=[chunk],
                ids=[doc_id],
                metadatas=[metadata]
            )
            total_chunks += 1

    print(f"✓ Successfully ingested {total_chunks} chunks from {len(files)} files")
    if branch_id:
        print(f"✓ Branch-specific FAQs indexed for: {branch_id}")

if __name__ == "__main__":
    import sys
    branch = sys.argv[1] if len(sys.argv) > 1 else None
    clear = "--clear" in sys.argv
    ingest_faqs(branch_id=branch, clear_existing=clear)
