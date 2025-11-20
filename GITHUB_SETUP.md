# GitHub Setup Guide

## ✅ Git Repository Initialized

Your repository is ready! Here's how to push to GitHub:

## 🚀 Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Create a new repository (e.g., `hiva-ai-assistant`)
3. **Don't** initialize with README, .gitignore, or license (we already have these)
4. Copy the repository URL (e.g., `https://github.com/yourusername/hiva-ai-assistant.git`)

## 🔗 Step 2: Add Remote and Push

Replace `YOUR_GITHUB_URL` with your actual repository URL:

```bash
cd /root/hiva

# Add remote
git remote add origin YOUR_GITHUB_URL

# Push to GitHub
git push -u origin main
```

### Example:
```bash
git remote add origin https://github.com/yourusername/hiva-ai-assistant.git
git push -u origin main
```

## 🔐 Step 3: Authentication

If you need to authenticate:

### Option A: Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate token with `repo` scope
3. Use token as password when pushing

### Option B: SSH Key
```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub → Settings → SSH and GPG keys
# Then use SSH URL:
git remote set-url origin git@github.com:yourusername/hiva-ai-assistant.git
```

## 📦 What's Included

Your repository includes:
- ✅ All source code
- ✅ Configuration files
- ✅ Documentation
- ✅ Branch FAQ documents
- ✅ .gitignore (excludes venv, db, etc.)

## 🚫 What's Excluded (.gitignore)

- Virtual environment (`venv/`)
- Database files (`*.db`, `*.sqlite3`)
- Environment variables (`.env`)
- Model files (too large)
- Cache files
- IDE files

## 🔄 Future Updates

After making changes:

```bash
cd /root/hiva
git add .
git commit -m "Your commit message"
git push
```

## 📝 Branch Strategy

Current branch: `main`

To create feature branches:
```bash
git checkout -b feature/new-feature
# Make changes
git commit -m "Add new feature"
git push -u origin feature/new-feature
```

## 🎯 Quick Commands

```bash
# Check status
git status

# See what changed
git diff

# View commit history
git log --oneline

# Push changes
git push
```

