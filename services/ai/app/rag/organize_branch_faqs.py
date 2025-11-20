#!/usr/bin/env python3
"""
Organize branch FAQ files from /root/hiva/docs to the proper structure
"""
import os
import shutil
import re
from pathlib import Path

# Source directory
SOURCE_DIR = "/root/hiva/docs"
# Target directory
TARGET_DIR = "/root/hiva/services/ai/app/rag/faqs"

# Branch name mapping from file names to branch IDs
BRANCH_MAPPING = {
    "kano": "kano",
    "kogi": "kogi", 
    "kaduna": "kaduna",
    "fct": "fct",
    "adamawa": "adamawa",
    "zamfara": "zamfara",
    "sokoto": "sokoto",
    "rivers": "rivers",
    "osun": "osun"
}

def extract_branch_from_filename(filename: str) -> str:
    """Extract branch ID from filename"""
    filename_lower = filename.lower()
    
    # Try to match branch names
    for branch_name, branch_id in BRANCH_MAPPING.items():
        if branch_name in filename_lower:
            return branch_id
    
    # Try to extract from patterns like "KSCHMA(KANO)" -> "kano"
    match = re.search(r'\(([A-Z]+)\)', filename.upper())
    if match:
        abbrev = match.group(1)
        # Map abbreviations to branch IDs
        abbrev_map = {
            "KANO": "kano",
            "KOGI": "kogi",
            "KADUNA": "kaduna", 
            "FCT": "fct",
            "ADAMAWA": "adamawa",
            "ZAMFARA": "zamfara",
            "SOKOTO": "sokoto",
            "RIVERS": "rivers",
            "OSUN": "osun"
        }
        if abbrev in abbrev_map:
            return abbrev_map[abbrev]
    
    return None

def organize_faqs():
    """Organize FAQ files into branch-specific directories"""
    print("📁 Organizing branch FAQ files...")
    
    # Create target directories
    os.makedirs(TARGET_DIR, exist_ok=True)
    branches_dir = os.path.join(TARGET_DIR, "branches")
    os.makedirs(branches_dir, exist_ok=True)
    
    # Process files in source directory
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return
    
    files = [f for f in os.listdir(SOURCE_DIR) if f.endswith(('.docx', '.pdf', '.txt', '.md'))]
    
    if not files:
        print(f"⚠️  No FAQ files found in {SOURCE_DIR}")
        return
    
    print(f"Found {len(files)} FAQ files")
    
    organized = 0
    for filename in files:
        source_path = os.path.join(SOURCE_DIR, filename)
        
        # Extract branch ID
        branch_id = extract_branch_from_filename(filename)
        
        if branch_id:
            # Create branch directory
            branch_dir = os.path.join(branches_dir, branch_id)
            os.makedirs(branch_dir, exist_ok=True)
            
            # Copy file to branch directory
            target_path = os.path.join(branch_dir, filename)
            shutil.copy2(source_path, target_path)
            print(f"✓ {filename} -> branches/{branch_id}/")
            organized += 1
        else:
            # Copy to general FAQs if branch not identified
            target_path = os.path.join(TARGET_DIR, filename)
            shutil.copy2(source_path, target_path)
            print(f"⚠️  {filename} -> (general, branch not identified)")
            organized += 1
    
    print(f"\n✅ Organized {organized} files")
    print(f"📁 Files are now in: {TARGET_DIR}")

if __name__ == "__main__":
    organize_faqs()

