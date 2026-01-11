# Providers Knowledge Base

This folder contains FAQ and policy documents for general healthcare providers.

## Supported File Formats

- **PDF** (`.pdf`)
- **Word Documents** (`.docx`)
- **Text Files** (`.txt`)
- **Markdown** (`.md`)

## Adding Documents

1. Place your provider documents in this folder
2. Run the ingestion script:
   ```bash
   python -m app.state_kb.ingest providers
   ```

3. The documents will be automatically processed and indexed for retrieval via the `/api/v1/providers/ask` endpoint.

## Example Structure

```
providers/
├── provider_guidelines.pdf
├── provider_faqs.docx
├── enrollment_procedures.txt
└── billing_policies.md
```

