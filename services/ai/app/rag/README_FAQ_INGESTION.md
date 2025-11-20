# FAQ Ingestion Guide for 9 Branches

## 📁 Recommended File Structure

Organize your FAQs like this:

```
services/ai/app/rag/faqs/
├── general_faqs.pdf              # Company-wide FAQs
├── company_policies.pdf          # General policies
├── branches/
│   ├── lagos/
│   │   ├── lagos_policies.pdf
│   │   ├── lagos_procedures.txt
│   │   └── lagos_contact_info.md
│   ├── abuja/
│   │   ├── abuja_policies.pdf
│   │   └── abuja_faqs.txt
│   ├── port-harcourt/
│   │   └── ph_faqs.pdf
│   ├── kano/
│   │   └── kano_policies.pdf
│   └── ... (other 5 branches)
```

## 🚀 How to Ingest FAQs

### Option 1: Ingest All FAQs (Recommended First Time)

```bash
cd /root/hiva
source venv/bin/activate
cd services/ai
python -m app.rag.ingest
```

This will:
- Process all FAQs from all branches
- Index general FAQs (available to all branches)
- Index branch-specific FAQs (tagged with branch_id)

### Option 2: Ingest Specific Branch

```bash
# Ingest only Lagos branch FAQs
python -m app.rag.ingest lagos

# Ingest only Abuja branch FAQs
python -m app.rag.ingest abuja
```

### Option 3: Clear and Re-ingest Everything

```bash
# Clear existing index and re-ingest all FAQs
python -m app.rag.ingest --clear
```

## 📝 Supported File Formats

- **PDF** (`.pdf`) - Automatically extracted
- **Text** (`.txt`) - Plain text files
- **Markdown** (`.md`) - Markdown formatted files

## 🎯 How Branch Filtering Works

1. **General FAQs** (in `faqs/` root):
   - Available to ALL branches
   - No branch_id metadata

2. **Branch-Specific FAQs** (in `faqs/branches/{branch_id}/`):
   - Tagged with branch_id metadata
   - When user queries with `branch_id`, system prioritizes:
     - First: Branch-specific FAQs
     - Then: General FAQs (if needed)

## 🔍 Example Usage

### API Request with Branch

```bash
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are your claim procedures?",
    "session_id": "test123",
    "branch_id": "lagos"
  }'
```

The system will:
1. Search Lagos-specific FAQs first
2. Fall back to general FAQs if needed
3. Provide branch-aware responses

## 📊 Best Practices

1. **Upload All Branch FAQs**: Yes! The more data, the better the AI responses
2. **Organize by Branch**: Use the `branches/` folder structure
3. **Include General FAQs**: Put company-wide info in the root `faqs/` folder
4. **Update Regularly**: Re-run ingestion when you add new FAQs
5. **Use Clear Filenames**: Helps with debugging and organization

## 🔄 Updating FAQs

When you add new FAQs:

```bash
# Just re-run ingestion (it will add new files, not duplicate)
python -m app.rag.ingest

# Or for a specific branch
python -m app.rag.ingest lagos
```

## ⚠️ Important Notes

- **First Run**: Will download the embedding model (~33MB, one-time)
- **Processing Time**: Depends on FAQ size (typically 1-5 minutes for all branches)
- **Memory**: Each chunk uses ~1KB, so 10,000 chunks ≈ 10MB
- **No Duplicates**: Same file won't be indexed twice (based on file path)

## 🎯 Branch IDs

Make sure your branch IDs match what you configure in:
- `app/services/branch_config.py`
- API requests (`branch_id` parameter)

Common branch IDs:
- `lagos`, `abuja`, `port-harcourt`, `kano`, `ibadan`, `benin`, `calabar`, `enugu`, `kaduna`

