# Branch Detection Guide

## 🎯 How Branch Detection Works

The system uses **smart branch detection** with 3 levels of priority:

### Priority 1: Explicit Branch ID (Highest)
If you explicitly provide `branch_id` in the request, it's used immediately.

```json
{
  "query": "What is the enrollment process?",
  "branch_id": "kano"
}
```

### Priority 2: Query Detection
The system automatically detects branch mentions in the user's query.

**Detected patterns:**
- Branch names: "kano", "kogi", "kaduna", "fct", "adamawa", "zamfara", "sokoto", "rivers", "osun"
- Abbreviations: "KSCHMA", "KGSHIA", "KADCHMA", "FHIS", "ASCHMA", "ZAMCHEMA", "SOHEMA", "RIVCHPP", "OSHIA"
- Alternative names: "abuja" → "fct", "port harcourt" → "rivers"

**Examples:**
```json
// User query: "What are KSCHMA policies?"
// → Automatically detects: branch_id = "kano"

// User query: "Tell me about Rivers enrollment"
// → Automatically detects: branch_id = "rivers"

// User query: "FHIS procedures"
// → Automatically detects: branch_id = "fct"
```

### Priority 3: Session History
If the user mentioned a branch in previous messages, it's remembered for the session.

**Example conversation:**
```
User: "I'm from Kano, what are your policies?"
System: [Detects "kano" and remembers for session]

User: "How do I enroll?"
System: [Uses "kano" from previous message]
```

## 📡 API Usage

### Method 1: Explicit Branch ID (Recommended for Web Apps)

```bash
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the enrollment process?",
    "session_id": "user123",
    "branch_id": "kano"
  }'
```

### Method 2: Automatic Detection (Natural Language)

```bash
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are KSCHMA enrollment requirements?",
    "session_id": "user123"
  }'
```

The system will automatically detect "KSCHMA" → "kano"

### Method 3: Session-Based (Conversational)

```bash
# First message - mentions branch
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I am from Rivers state, what are your policies?",
    "session_id": "user123"
  }'

# Subsequent messages - branch remembered
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I enroll?",
    "session_id": "user123"
  }'
```

## 🔍 Detection Examples

| User Query | Detected Branch | Method |
|------------|----------------|--------|
| "KSCHMA policies" | `kano` | Abbreviation |
| "I'm in Kano" | `kano` | Branch name |
| "Rivers enrollment" | `rivers` | Branch name |
| "Port Harcourt FAQ" | `rivers` | Alternative name |
| "FHIS procedures" | `fct` | Abbreviation |
| "Abuja branch info" | `fct` | Alternative name |
| "KGSHIA requirements" | `kogi` | Abbreviation |

## 🎨 Frontend Integration

### Option 1: Branch Selector (Recommended)

```javascript
// User selects branch from dropdown
const branchId = document.getElementById('branch-selector').value;

fetch('/api/v1/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: userQuery,
    session_id: sessionId,
    branch_id: branchId  // Explicit - highest priority
  })
});
```

### Option 2: Natural Language (Auto-Detection)

```javascript
// Let the system detect from query
fetch('/api/v1/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: "What are KSCHMA policies?",  // System detects "kano"
    session_id: sessionId
  })
});
```

## 📊 Branch IDs Reference

| Branch ID | Full Name | Abbreviations | Alternative Names |
|-----------|-----------|---------------|-------------------|
| `kano` | KSCHMA Kano | KSCHMA | - |
| `kogi` | KGSHIA Kogi | KGSHIA | - |
| `kaduna` | KADCHMA Kaduna | KADCHMA | - |
| `fct` | FHIS FCT | FHIS | abuja, federal capital territory |
| `adamawa` | ASCHMA Adamawa | ASCHMA | - |
| `zamfara` | ZAMCHEMA Zamfara | ZAMCHEMA | - |
| `sokoto` | SOHEMA Sokoto | SOHEMA | - |
| `rivers` | RIVCHPP Rivers | RIVCHPP | port harcourt |
| `osun` | OSHIA Osun | OSHIA | - |

## 🔄 Session Persistence

Branch information persists within a session:

1. **First message**: User mentions "I'm from Kano"
2. **System remembers**: `branch_id = "kano"` for this session
3. **Subsequent messages**: Automatically uses Kano branch context
4. **Session expires**: After 24 hours (configurable)

## ⚙️ Configuration

Branch detection is automatic and requires no configuration. However, you can:

1. **Add custom keywords** in `app/services/branch_detector.py`
2. **Modify detection logic** for your specific use case
3. **Adjust session TTL** in `conversation_manager.py`

## 🎯 Best Practices

1. **Use explicit branch_id** for web apps with branch selectors
2. **Let auto-detection work** for natural language queries
3. **Maintain session_id** across requests for conversation continuity
4. **Clear session** when user switches branches explicitly

## 🐛 Troubleshooting

**Q: Branch not detected?**
- Check if branch name/abbreviation is in the detection list
- Try using explicit `branch_id` parameter
- Check spelling (case-insensitive)

**Q: Wrong branch detected?**
- Use explicit `branch_id` to override
- Clear session and start fresh
- Check for ambiguous queries (e.g., "rivers" could be state or river)

**Q: Branch forgotten in session?**
- Sessions expire after 24 hours
- Branch is remembered per session_id
- Use same session_id to maintain context

