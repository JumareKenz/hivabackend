# State Knowledge Base Folders

This directory contains FAQ and policy documents for each Nigerian state.

## Folder Structure

Each state has its own dedicated folder:
- `adamawa/` - Adamawa State (ASCHMA)
- `fct/` - Federal Capital Territory (FHIS)
- `kano/` - Kano State (KSCHMA)
- `zamfara/` - Zamfara State (ZAMCHEMA)
- `kogi/` - Kogi State (KGSHIA)
- `osun/` - Osun State (OSHIA)
- `rivers/` - Rivers State (RIVCHPP)
- `sokoto/` - Sokoto State (SOHEMA)
- `kaduna/` - Kaduna State (KADCHMA)

## Supported File Formats

Place your FAQ and policy documents in the respective state folders. Supported formats:
- **PDF** (`.pdf`)
- **Word Documents** (`.docx`)
- **Text Files** (`.txt`)
- **Markdown** (`.md`)

## Adding Documents

1. Place your documents in the appropriate state folder
2. Run the ingestion script:
   ```bash
   python -m app.state_kb.ingest <state_id>
   ```
   For example: `python -m app.state_kb.ingest adamawa`

3. The documents will be automatically:
   - Extracted and processed
   - Chunked into smaller pieces
   - Embedded using state-of-the-art models
   - Indexed in ChromaDB for fast retrieval

## Example

```
branches/
├── adamawa/
│   ├── ASCHMA_FAQ.docx
│   ├── Adamawa_Policies.pdf
│   └── enrollment_procedures.txt
├── kano/
│   ├── KSCHMA_FAQ.docx
│   └── Kano_Policies.pdf
└── ...
```

