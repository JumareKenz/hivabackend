# Firewall Setup for Admin Chat Service

## Server-Side Configuration ✅ COMPLETE

The service is now configured to:
- Listen on `0.0.0.0:8001` (all interfaces)
- UFW firewall rule added for port 8001
- Service running and accessible locally

## Cloud Provider Firewall (If Applicable)

If you're using a cloud provider (AWS, DigitalOcean, Azure, etc.), you may need to open port 8001 in their firewall/security group:

### DigitalOcean
1. Go to Networking → Firewalls
2. Create or edit firewall rules
3. Add inbound rule: TCP port 8001, allow from 0.0.0.0/0 (or specific IPs)

### AWS EC2
1. Go to EC2 → Security Groups
2. Select your instance's security group
3. Add inbound rule: Type: Custom TCP, Port: 8001, Source: 0.0.0.0/0 (or specific IPs)

### Azure
1. Go to Network Security Groups
2. Add inbound security rule: Port 8001, Protocol: TCP

### Contabo (Current Provider)
If using Contabo, check:
1. Contabo Control Panel → Networking
2. Firewall rules for your VPS
3. Ensure port 8001 is open

## Testing from Windows

From PowerShell:
```powershell
Test-NetConnection -ComputerName 194.163.168.161 -Port 8001
```

Expected result: `TcpTestSucceeded : True`

## Current Status

- ✅ Service listening on 0.0.0.0:8001
- ✅ UFW firewall rule added
- ✅ Service accessible locally
- ⚠️ If external connection fails, check cloud provider firewall





