# MCP Mode Disabled - Strategic Decision

## Overview

MCP (Model Context Protocol) mode has been **strategically disabled** to ensure all queries go through the Phase 4 validator and Domain 3 governance layers.

## Rationale

### Critical Requirements

1. **Phase 4 Validator**: The SQL validator is integrated into `_handle_query_legacy` and must run for all queries to ensure:
   - Canonical join paths are enforced
   - Forbidden patterns (e.g., `c.diagnosis`) are rejected
   - Human-readable labels are required
   - IDs and codes are blocked

2. **Domain 3 Governance**: Legacy mode includes:
   - Query Intelligence & Reasoning Control
   - Safety, Permissions & Data Governance
   - Explainability & Trust Layer
   - Performance, Cost & Reliability Controls
   - Evaluation & KPIs

3. **MCP Mode Gap**: `_handle_query_via_mcp` does not include:
   - Phase 4 SQL Validator
   - Phase 4 SQL Rewriter
   - Phase 4 Confidence Scorer
   - Phase 4 Result Sanitizer
   - Domain 3 governance layers

## Changes Made

### 1. Configuration (`app/core/config.py`)
- `USE_MCP_MODE`: Set to `False` with clear documentation
- `MCP_GRADUAL_ROLLOUT`: Set to `0.0` (no MCP traffic)
- Added comments explaining why MCP is disabled

### 2. API Handler (`app/api/v1/admin.py`)
- Removed MCP client import (set to `None`)
- Removed MCP routing logic
- Disabled `_handle_query_via_mcp` function
- All queries now route directly to `_handle_query_legacy`

### 3. Code Cleanup
- Removed debug logging related to MCP mode
- Added clear comments explaining the decision
- Maintained code structure for future MCP integration if needed

## Current Architecture

```
User Query
    ↓
admin_query_data() endpoint
    ↓
_handle_data_query()
    ↓
_handle_query_legacy() ← All queries go here
    ↓
Phase 4 Validator ← CRITICAL: Must run for all queries
    ↓
[Other Phase 4 & Domain 3 layers]
    ↓
Query Execution
```

## Future Considerations

If MCP mode is needed in the future, it must be updated to include:

1. **Phase 4 Integration**:
   - SQL Validator (STRICT - HARD FAIL)
   - SQL Rewriter (SOFT CORRECTION)
   - Confidence Scorer
   - Result Sanitizer

2. **Domain 3 Integration**:
   - Query Intelligence
   - Safety & Governance
   - Explainability
   - Performance Controls
   - Evaluation Metrics

3. **Testing**:
   - Comprehensive validation testing
   - Performance benchmarking
   - Security audit

## Status

✅ **MCP Mode: DISABLED**  
✅ **Legacy Mode: ACTIVE** (with all Phase 4 & Domain 3 layers)  
✅ **Validator: ACTIVE** (runs for all queries)

## Verification

To verify MCP is disabled:
```python
from app.core.config import settings
assert settings.USE_MCP_MODE == False
```

All queries will now go through the validated, governed legacy path.



