# Router System Documentation
## Intent Classification and Routing

**Version**: 1.0.0  
**Date**: 2025-01-27  
**Status**: Production Active

---

## Overview

The Router System intelligently classifies user queries as either **[DATA]** or **[CHAT]** and routes them to the appropriate handler. This ensures that:

- **Data queries** go to the MCP-enabled Data Specialist (with database tools)
- **General conversation** goes to the Chat Handler (standard LLM, no tools)

---

## Architecture

```
User Query
    ↓
Intent Router (Classifies: [DATA] or [CHAT])
    ↓
    ├─ [CHAT] → Chat Handler → Standard LLM (no tools)
    └─ [DATA] → Data Handler → MCP Server (with tools)
```

---

## Components

### 1. Intent Router (`app/services/intent_router.py`)

**Purpose**: Classifies user intent

**Classification Rules**:
- **[CHAT]**: Greetings, social questions, capability questions
- **[DATA]**: Numbers, claims, records, lists, statistics, status updates

**Fast-Path Classification**:
- Greetings: "hello", "hi", "hey" → CHAT
- Social: "how are you", "what can you do" → CHAT
- Data keywords: "show", "count", "total", "claims" → DATA
- Ambiguous: Uses LLM with low temperature (0.0)

### 2. Chat Handler (`app/services/chat_handler.py`)

**Purpose**: Handles general conversation

**Features**:
- Uses standard LLM (no MCP tools)
- Friendly, helpful responses
- Guides users to data queries
- Maintains conversation context

**System Prompt**:
```
You are a helpful assistant for the HIVA Admin Chat service.
- Answer questions about capabilities
- Provide guidance on data queries
- Engage in friendly conversation
```

### 3. Data Handler (MCP or Legacy)

**Purpose**: Handles data queries

**Features**:
- Uses MCP tools (if enabled)
- Data Specialist prompt
- SQL generation and execution
- Visualization creation

**System Prompt**:
```
You are a SQL Data Expert. You have access to tools via MCP.

Rules:
- No Guessing: Ask for clarification if query is vague
- Validation: Explain what you're searching for
- Empty Results: State "No records found" (don't hallucinate)
```

---

## Router Prompt

### System Prompt

```
You are an Intent Classifier. Your only job is to determine if a user wants to talk to the database or have a general conversation.

Categories:

[DATA]: Use this if the user asks for numbers, claims, records, lists, statistics, or status updates on data.

[CHAT]: Use this for greetings ("hi", "hello"), social questions ("how are you"), or asking what the tool can do.

Rules:

Respond ONLY with the tag [DATA] or [CHAT].

If you are unsure, default to [CHAT].

Never execute a command. Just classify.
```

**Temperature**: 0.0 (very low for consistent classification)

---

## Data Specialist Prompt

### System Prompt

```
You are a SQL Data Expert. You have access to tools via MCP.

Operational Guidelines:

No Guessing: If a query is vague (e.g., "show claims"), do not default to "today." Ask the user: "What time period should I look at?"

Identity: You only respond to data requests.

Validation: Before running a tool, explain briefly what you are searching for.

Empty Results: If a query returns 0 results, do not hallucinate. State "No records found matching those criteria."

You have access to the following tools:
- generate_sql: Generate SQL queries from natural language
- execute_query: Execute SQL queries and get results
- get_schema: Get database schema information
- create_visualization: Create charts and visualizations
- manage_conversation: Manage conversation context
```

---

## MCP Tool Descriptions (Refined)

### generate_sql

**Before**:
```
"Generate SQL query from natural language"
```

**After**:
```
"Use this tool ONLY when the user explicitly asks for data queries, statistics, records, or lists from the database. Requires a specific data request (e.g., 'show me claims', 'total number of users', 'claims by status'). Do NOT use for greetings, general conversation, or questions about capabilities. If the query is vague (e.g., 'show claims' without a time period), ask the user for clarification before generating SQL."
```

### execute_query

**Before**:
```
"Execute a SQL SELECT query"
```

**After**:
```
"Use this tool ONLY to execute a SQL SELECT query that has already been generated. This tool runs read-only database queries and returns results with visualizations. Do NOT use for generating SQL (use generate_sql instead). Only use when you have a valid SQL SELECT statement ready to execute."
```

### get_schema

**Before**:
```
"Get database schema information"
```

**After**:
```
"Use this tool ONLY when you need to check database structure, table names, or column information before generating SQL. Use when the user's query mentions a table name you're unsure about, or when you need to verify column names exist. Do NOT use for general queries - only when schema information is specifically needed."
```

### create_visualization

**Before**:
```
"Create visualization from query results"
```

**After**:
```
"Use this tool ONLY when the user explicitly requests a chart, graph, or visualization (e.g., 'show as chart', 'create a graph', 'visualize this data'). Also use when query results contain numeric data that would benefit from visualization. Do NOT use for simple text responses or when the user only wants raw data."
```

### manage_conversation

**Before**:
```
"Manage conversation history and context"
```

**After**:
```
"Use this tool ONLY for managing conversation context, retrieving previous conversation history, or clearing session data. Use 'get_history' to retrieve past messages in the session, 'get_summary' to get a conversation summary, or 'clear_history' to reset the conversation. Do NOT use for answering user queries or generating responses."
```

---

## Implementation Flow

### Step 1: User Input
```python
user_query = "Show me total number of claims"
```

### Step 2: Intent Classification
```python
intent = await intent_router.classify_intent(user_query)
# Returns: "DATA"
```

### Step 3: Routing
```python
if intent == "CHAT":
    response = await chat_handler.handle_chat(user_query)
else:  # intent == "DATA"
    response = await _handle_data_query(user_query)
```

### Step 4: Processing
- **CHAT**: Standard LLM response (no tools)
- **DATA**: MCP tools → SQL generation → Query execution → Results

---

## Examples

### Example 1: Chat Query

**Input**: "Hello, how are you?"

**Classification**: [CHAT]

**Handler**: Chat Handler

**Response**: "Hello! I'm doing great, thank you for asking! 😊 How can I help you today with the HIVA data analytics system?"

**Tools Used**: None

---

### Example 2: Data Query

**Input**: "Show me total number of claims"

**Classification**: [DATA]

**Handler**: Data Handler (MCP)

**Process**:
1. Data Specialist prompt applied
2. `generate_sql` tool called
3. SQL generated: `SELECT COUNT(*) as total_claims FROM claims`
4. `execute_query` tool called
5. Results returned with visualization

**Tools Used**: generate_sql, execute_query

---

### Example 3: Vague Query

**Input**: "show claims"

**Classification**: [DATA]

**Handler**: Data Handler (MCP)

**Process**:
1. Data Specialist detects vague query
2. Asks for clarification: "What time period should I look at?"

**Tools Used**: None (clarification needed)

---

## Benefits

### 1. **Prevents Tool Misuse**
- Chat queries don't trigger database tools
- Data queries get proper tool access
- Clear separation of concerns

### 2. **Better User Experience**
- Friendly responses for greetings
- Accurate data queries
- No confusion between chat and data

### 3. **Improved Accuracy**
- Data Specialist prompt prevents guessing
- Asks for clarification when needed
- No hallucination on empty results

### 4. **Performance**
- Fast-path classification (no LLM needed for obvious cases)
- Appropriate tool usage
- Reduced unnecessary API calls

---

## Testing

### Test Intent Classification

```bash
python test_router_system.py
```

**Test Cases**:
- ✅ Greetings → CHAT
- ✅ Social questions → CHAT
- ✅ Data queries → DATA
- ✅ Ambiguous queries → Uses LLM

### Test Chat Handler

```bash
# Test chat responses
curl -X POST http://localhost:8001/api/v1/admin/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"query": "hello"}'
```

### Test Data Handler

```bash
# Test data queries
curl -X POST http://localhost:8001/api/v1/admin/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"query": "Show me total number of claims"}'
```

---

## Configuration

### Router Settings

**Temperature**: 0.0 (for consistent classification)

**Fast-Path Keywords**:
- CHAT: greetings, social patterns
- DATA: show, count, total, claims, etc.

### Data Specialist Settings

**Temperature**: 0.1 (low for SQL accuracy)

**Validation**: Enabled (asks for clarification)

**Empty Results**: Explicit "No records found" message

---

## Monitoring

### Metrics to Track

1. **Classification Accuracy**
   - CHAT vs DATA accuracy
   - False positives/negatives

2. **Response Times**
   - Router classification time
   - Chat handler response time
   - Data handler response time

3. **Tool Usage**
   - Which tools are used most
   - Tool misuse (if any)

### Logging

```python
# Intent classification logged
metadata = {
    "intent": "DATA" or "CHAT",
    "mode": "mcp" or "legacy" or "chat",
    "query": user_query
}
```

---

## Troubleshooting

### Issue: All queries classified as CHAT

**Solution**: Check fast-path keywords and LLM classification

### Issue: Data queries not using tools

**Solution**: Verify MCP mode is enabled and tools are registered

### Issue: Vague queries not asking for clarification

**Solution**: Ensure Data Specialist prompt is being used

---

## Best Practices

### ✅ DO

- Use clear, specific data queries
- Include time periods in queries
- Use session IDs for follow-ups

### ❌ DON'T

- Use vague queries without context
- Mix chat and data in one query
- Skip session IDs for follow-ups

---

## Future Enhancements

1. **Multi-Intent Support**: Handle queries with both chat and data
2. **Confidence Scores**: Return classification confidence
3. **Learning**: Improve classification based on user feedback
4. **Custom Intents**: Add domain-specific intent categories

---

## References

- **Router Implementation**: `app/services/intent_router.py`
- **Chat Handler**: `app/services/chat_handler.py`
- **API Integration**: `app/api/v1/admin.py`
- **Test Suite**: `test_router_system.py`

---

*Last Updated: 2025-01-27*  
*Status: Production Active*

