# Admin SQL Chat - Test Mode

## ✅ Test Mode Available (No Database Required)

A test mode has been added for the admin SQL chat feature that allows you to test SQL generation and chat functionality **without a live database connection**.

## 🎯 Features

### Test Endpoints (No Authentication Required)

1. **`POST /api/v1/admin/test/query`**
   - Test SQL generation from natural language
   - Get mock query results
   - Test visualization and summary generation
   - Test conversation context handling

2. **`GET /api/v1/admin/test/schema`**
   - View mock database schema
   - Understand available tables and columns

3. **`GET /api/v1/admin/test/health`**
   - Check test mode availability
   - View available features

## 📝 Usage Examples

### Test SQL Generation

```bash
# Test basic query
curl -X POST http://localhost:8000/api/v1/admin/test/query \
  -H "Content-Type: application/json" \
  -d '{"query": "How many users are in the database?"}'

# Test with conversation context
curl -X POST http://localhost:8000/api/v1/admin/test/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What about enrollments?",
    "session_id": "test-session-123",
    "refine_query": true
  }'
```

### View Mock Schema

```bash
curl http://localhost:8000/api/v1/admin/test/schema
```

### Check Health

```bash
curl http://localhost:8000/api/v1/admin/test/health
```

## 🗄️ Mock Database Schema

The test mode includes a mock schema with these tables:

1. **users**
   - id, name, email, created_at, branch_id

2. **enrollments**
   - id, user_id, plan_type, status, enrolled_at

3. **claims**
   - id, enrollment_id, amount, status, submitted_at

## 🔄 Response Format

```json
{
  "success": true,
  "sql": "SELECT COUNT(*) as count FROM users",
  "sql_explanation": "Counts total users in database",
  "confidence": 0.95,
  "data": [...],
  "visualization": {...},
  "summary": "...",
  "session_id": "...",
  "test_mode": true
}
```

## ✅ Benefits

- **No Database Required**: Test SQL generation without database setup
- **No Authentication**: Quick testing without API keys
- **Full Functionality**: Test all features except actual database execution
- **Mock Data**: Realistic sample data for testing visualizations

## 🚀 When to Use

- **Development**: Test SQL generation logic
- **Debugging**: Verify query explanations and confidence scores
- **Demo**: Show functionality without database access
- **Testing**: Validate conversation context handling

## 📊 Limitations

- Mock data is simplified (not real database results)
- Limited to predefined mock tables
- No actual SQL execution validation
- Results are simulated, not from real queries

## 🔗 Production Endpoint

For production use with real database:
- `POST /api/v1/admin/query` (requires authentication)
- `GET /api/v1/admin/schema` (requires authentication)

---

**Test Mode Status**: ✅ Enabled
**Database Required**: ❌ No
**Authentication Required**: ❌ No

