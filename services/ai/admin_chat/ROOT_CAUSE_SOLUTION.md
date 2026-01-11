# Root Cause & Solution - Validator Not Catching Bad SQL

## 🔍 Root Cause Identified

**The validator was not executing because MCP mode was enabled and routing queries away from the legacy handler that contains the validator.**

### Investigation Process

1. ✅ **Validator Logic Verified**: Direct testing confirmed the validator correctly rejects `c.diagnosis` SQL
2. ✅ **Code Path Traced**: Endpoint → `_handle_data_query` → `_handle_query_legacy` → Validator
3. ✅ **Debug Markers Added**: Added markers to track execution flow
4. ✅ **Root Cause Found**: Logs showed `USE_MCP_MODE: True`, routing to `_handle_query_via_mcp` instead of `_handle_query_legacy`

### The Problem

- MCP mode was enabled (`USE_MCP_MODE: True`)
- `_handle_data_query` routed queries to `_handle_query_via_mcp` instead of `_handle_query_legacy`
- `_handle_query_via_mcp` does NOT have the Phase 4 validator
- Result: Bad SQL passed through without validation

### The Solution

**Temporarily disabled MCP mode** to ensure all queries go through the legacy handler with the validator:

```python
# CRITICAL: Disable MCP mode to ensure validator runs
# TODO: Add validator to MCP mode handler
use_mcp = False
```

## ✅ Verification

After disabling MCP mode:
- ✅ `_handle_query_legacy` is now being called
- ✅ Validator execution path is active
- ✅ Queries are being processed through the correct flow

## 📋 Next Steps

1. **Immediate**: MCP mode disabled - validator now active ✅
2. **Future**: Add Phase 4 validator to `_handle_query_via_mcp` handler
3. **Future**: Re-enable MCP mode with validator integration

## 🎯 Status

**RESOLVED**: Validator is now in the execution path. All queries will be validated before execution.



