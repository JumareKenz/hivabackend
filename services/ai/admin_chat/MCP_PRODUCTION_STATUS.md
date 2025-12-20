# MCP Production Status

**Date Enabled**: 2025-01-27  
**Status**: ✅ **ACTIVE IN PRODUCTION**

---

## Configuration

### Current Settings

```bash
USE_MCP_MODE=true
MCP_GRADUAL_ROLLOUT=0.1  # 10% of traffic
MCP_FALLBACK_TO_LEGACY=true
```

### Service Status

- **Service**: `hiva-admin-chat.service`
- **Status**: ✅ Active (running)
- **Port**: 8001
- **MCP Mode**: ✅ Enabled
- **Rollout**: 10% of traffic

---

## Health Check

### Endpoint
```bash
GET /api/v1/admin/health
```

### Response
```json
{
    "status": "healthy",
    "database_available": true,
    "admin_features_enabled": true,
    "mcp_mode_enabled": true,
    "mcp_rollout_percentage": 0.1,
    "user": "admin"
}
```

---

## Rollout Plan

### Phase 1: Current (10%)
- **Status**: ✅ Active
- **Duration**: Monitor for 24-48 hours
- **Metrics to Watch**:
  - Error rate
  - Response times
  - Query accuracy
  - User feedback

### Phase 2: 25% (Next)
- **When**: After 24-48 hours of stable 10%
- **Action**: Update `MCP_GRADUAL_ROLLOUT=0.25`

### Phase 3: 50%
- **When**: After 24 hours of stable 25%
- **Action**: Update `MCP_GRADUAL_ROLLOUT=0.50`

### Phase 4: 75%
- **When**: After 24 hours of stable 50%
- **Action**: Update `MCP_GRADUAL_ROLLOUT=0.75`

### Phase 5: 100%
- **When**: After 24 hours of stable 75%
- **Action**: Update `MCP_GRADUAL_ROLLOUT=1.0`

---

## Monitoring

### Service Logs
```bash
sudo journalctl -u hiva-admin-chat -f
```

### Health Check
```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:8001/api/v1/admin/health
```

### Test Query
```bash
curl -X POST http://localhost:8001/api/v1/admin/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"query": "Show me total number of claims"}'
```

---

## Rollback Procedure

If issues occur, immediately rollback:

### Option 1: Disable MCP Mode
```bash
# Edit .env file
USE_MCP_MODE=false

# Restart service
sudo systemctl restart hiva-admin-chat
```

### Option 2: Reduce Rollout
```bash
# Edit .env file
MCP_GRADUAL_ROLLOUT=0.0

# Restart service
sudo systemctl restart hiva-admin-chat
```

### Option 3: Emergency Rollback
```bash
# Restore backup
cp /root/hiva/services/ai/.env.backup.* /root/hiva/services/ai/.env

# Restart service
sudo systemctl restart hiva-admin-chat
```

---

## Metrics to Monitor

### Performance
- Response time (target: < 1s)
- Query execution time
- SQL generation time

### Reliability
- Error rate (target: < 0.1%)
- Success rate (target: > 99.9%)
- Fallback frequency

### Data Integrity
- Query accuracy
- Result consistency
- Schema validation

---

## Troubleshooting

### MCP Mode Not Working

1. **Check configuration**:
   ```bash
   grep MCP /root/hiva/services/ai/.env
   ```

2. **Check service logs**:
   ```bash
   sudo journalctl -u hiva-admin-chat -n 50
   ```

3. **Test MCP client**:
   ```bash
   cd /root/hiva/services/ai/admin_chat
   source venv/bin/activate
   python test_mcp_integration.py
   ```

### High Error Rate

1. Check database connectivity
2. Review RunPod endpoint status
3. Check service resources (CPU, memory)
4. Review error logs

### Performance Issues

1. Check database connection pool
2. Review query execution times
3. Monitor system resources
4. Check for slow queries

---

## Next Steps

### Immediate (Next 24-48 hours)
- [x] Enable MCP mode (10% rollout)
- [ ] Monitor metrics and logs
- [ ] Collect user feedback
- [ ] Review error rates

### Short-term (Week 1)
- [ ] Increase to 25% if stable
- [ ] Continue monitoring
- [ ] Optimize based on metrics

### Medium-term (Week 2-4)
- [ ] Gradually increase to 100%
- [ ] Full production rollout
- [ ] Performance optimization

---

## Support

For issues or questions:
1. Check service logs
2. Review health endpoint
3. Run validation tests
4. Consult documentation

---

*Last Updated: 2025-01-27*  
*Status: Active in Production*


