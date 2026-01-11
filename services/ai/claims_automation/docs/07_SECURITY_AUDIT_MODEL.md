# Security Threat Model & Audit Specification

**Version:** 1.0.0  
**Date:** January 7, 2026  
**Classification:** CONFIDENTIAL - Security Document

---

## 1. Security Architecture Overview

### 1.1 Defense in Depth Strategy

```
                          DEFENSE IN DEPTH LAYERS
    ════════════════════════════════════════════════════════════════

    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 1: PERIMETER                           │
    │  • Web Application Firewall (WAF)                               │
    │  • DDoS Protection                                              │
    │  • Rate Limiting                                                │
    │  • IP Allowlisting (inter-service)                              │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 2: NETWORK                             │
    │  • Network Segmentation (VPC/Subnets)                          │
    │  • Zero Trust (mTLS everywhere)                                │
    │  • Private Endpoints                                            │
    │  • Network Policies (K8s)                                       │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 3: AUTHENTICATION                      │
    │  • mTLS (service-to-service)                                   │
    │  • JWT Tokens (API access)                                     │
    │  • OIDC + MFA (admin users)                                    │
    │  • API Keys (external systems)                                 │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 4: AUTHORIZATION                       │
    │  • Role-Based Access Control (RBAC)                            │
    │  • Attribute-Based Access Control (ABAC)                       │
    │  • Permission Boundaries                                        │
    │  • Resource-Level Permissions                                   │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 5: DATA                                │
    │  • Encryption at Rest (AES-256-GCM)                            │
    │  • Encryption in Transit (TLS 1.3)                             │
    │  • Data Masking / Tokenization                                 │
    │  • Key Management (HSM-backed)                                  │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 6: APPLICATION                         │
    │  • Input Validation                                             │
    │  • Output Encoding                                              │
    │  • Secure Coding Practices                                      │
    │  • Dependency Scanning                                          │
    └─────────────────────────────────────────────────────────────────┘
                                  │
    ┌─────────────────────────────────────────────────────────────────┐
    │                    LAYER 7: MONITORING                          │
    │  • Security Information & Event Management (SIEM)              │
    │  • Intrusion Detection System (IDS)                            │
    │  • Anomaly Detection                                            │
    │  • Audit Logging                                                │
    └─────────────────────────────────────────────────────────────────┘

    ════════════════════════════════════════════════════════════════
```

### 1.2 Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             TRUST BOUNDARY DIAGRAM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ZONE A: CLAIMS BACKEND (HIGH TRUST)                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Full PII access                                                   │  │
│   │  • Payment authority                                                 │  │
│   │  • Database write access                                             │  │
│   │  • Internal only                                                     │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│            │                                                                │
│            │ ═══════════════════════════════════════════                   │
│            │ TRUST BOUNDARY 1 (mTLS + Signed Messages)                     │
│            │ ═══════════════════════════════════════════                   │
│            ▼                                                                │
│   ZONE B: MESSAGE BROKER (MEDIUM-HIGH TRUST)                               │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Sanitized data only                                               │  │
│   │  • Encrypted storage                                                 │  │
│   │  • Topic-level ACLs                                                  │  │
│   │  • No PII storage                                                    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│            │                                                                │
│            │ ═══════════════════════════════════════════                   │
│            │ TRUST BOUNDARY 2 (mTLS + JWT)                                 │
│            │ ═══════════════════════════════════════════                   │
│            ▼                                                                │
│   ZONE C: AI ENGINE (MEDIUM TRUST)                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Read-only sanitized data                                          │  │
│   │  • No payment authority                                              │  │
│   │  • Isolated compute                                                  │  │
│   │  • Limited network access                                            │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│            │                                                                │
│            │ ═══════════════════════════════════════════                   │
│            │ TRUST BOUNDARY 3 (JWT + RBAC)                                 │
│            │ ═══════════════════════════════════════════                   │
│            ▼                                                                │
│   ZONE D: ADMIN PORTAL (LOW-MEDIUM TRUST)                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Human-facing interface                                            │  │
│   │  • MFA required                                                      │  │
│   │  • Session management                                                │  │
│   │  • Read-mostly access                                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│            │                                                                │
│            │ ═══════════════════════════════════════════                   │
│            │ TRUST BOUNDARY 4 (OIDC + MFA)                                 │
│            │ ═══════════════════════════════════════════                   │
│            ▼                                                                │
│   ZONE E: EXTERNAL USERS (UNTRUSTED)                                       │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  • Admin users                                                       │  │
│   │  • Authenticated but untrusted                                       │  │
│   │  • All actions logged                                                │  │
│   │  • Strict rate limiting                                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Threat Model (STRIDE Analysis)

### 2.1 Threat Categories

| Category | Description | Primary Mitigations |
|----------|-------------|---------------------|
| **Spoofing** | Impersonating users or services | mTLS, MFA, JWT validation |
| **Tampering** | Modifying data or code | Signed messages, integrity checks |
| **Repudiation** | Denying actions | Immutable audit logs, timestamps |
| **Information Disclosure** | Unauthorized data access | Encryption, access controls |
| **Denial of Service** | Disrupting availability | Rate limiting, circuit breakers |
| **Elevation of Privilege** | Gaining unauthorized access | RBAC, least privilege |

### 2.2 Detailed Threat Analysis

```yaml
threats:
  # ═══════════════════════════════════════════════════════════════════
  # SPOOFING THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-SPOOF-001"
    name: "Service Impersonation"
    category: SPOOFING
    description: "Attacker impersonates backend service to inject malicious claims"
    attack_vector: "Fake service sends forged claim events to Kafka"
    impact: HIGH
    likelihood: LOW
    mitigations:
      - "mTLS with certificate pinning"
      - "HMAC signature on all messages"
      - "IP allowlisting for Kafka producers"
      - "Certificate rotation every 90 days"
    detection:
      - "Certificate validation failures"
      - "Signature verification failures"
      - "Unauthorized IP connections"
    
  - id: "T-SPOOF-002"
    name: "Admin User Impersonation"
    category: SPOOFING
    description: "Attacker gains access to admin account"
    attack_vector: "Credential theft, phishing, session hijacking"
    impact: HIGH
    likelihood: MEDIUM
    mitigations:
      - "MFA required for all admin users"
      - "OIDC with enterprise SSO"
      - "Session timeout (30 min idle)"
      - "Device binding"
      - "Anomaly detection on login patterns"
    detection:
      - "Failed login attempts"
      - "Login from new location/device"
      - "Concurrent session alerts"

  # ═══════════════════════════════════════════════════════════════════
  # TAMPERING THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-TAMPER-001"
    name: "Message Tampering"
    category: TAMPERING
    description: "Attacker modifies claim events in transit"
    attack_vector: "Man-in-the-middle attack on message queue"
    impact: HIGH
    likelihood: LOW
    mitigations:
      - "TLS 1.3 for all communications"
      - "HMAC signature on message payloads"
      - "Message integrity verification at consumer"
      - "Kafka authentication (SASL)"
    detection:
      - "Signature verification failures"
      - "Schema validation failures"
      - "Checksum mismatches"
    
  - id: "T-TAMPER-002"
    name: "Rule Engine Manipulation"
    category: TAMPERING
    description: "Attacker modifies rule definitions to bypass checks"
    attack_vector: "Compromise rule store or deployment pipeline"
    impact: CRITICAL
    likelihood: LOW
    mitigations:
      - "Rule checksums and integrity verification"
      - "Immutable rule history"
      - "Dual approval for rule changes"
      - "Signed rule artifacts"
      - "Rule change audit logging"
    detection:
      - "Checksum validation on rule load"
      - "Unauthorized rule change alerts"
      - "Drift detection between stored and loaded rules"
    
  - id: "T-TAMPER-003"
    name: "ML Model Poisoning"
    category: TAMPERING
    description: "Attacker manipulates training data or model weights"
    attack_vector: "Inject malicious feedback or modify model artifacts"
    impact: HIGH
    likelihood: LOW
    mitigations:
      - "Training data provenance tracking"
      - "Model artifact signing"
      - "Human approval for all model updates"
      - "Offline training only"
      - "No autonomous learning"
    detection:
      - "Model performance drift detection"
      - "Training data anomaly detection"
      - "Model hash verification on load"
    
  - id: "T-TAMPER-004"
    name: "Audit Log Tampering"
    category: TAMPERING
    description: "Attacker modifies or deletes audit records"
    attack_vector: "Database access or admin privilege abuse"
    impact: CRITICAL
    likelihood: LOW
    mitigations:
      - "Append-only audit tables"
      - "Database triggers preventing UPDATE/DELETE"
      - "Cryptographic chaining of audit records"
      - "Write-once storage (S3 Object Lock)"
      - "Log replication to SIEM"
    detection:
      - "Chain integrity verification"
      - "Sequence gap detection"
      - "Cross-reference with SIEM copy"

  # ═══════════════════════════════════════════════════════════════════
  # REPUDIATION THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-REPUD-001"
    name: "Decision Repudiation"
    category: REPUDIATION
    description: "Reviewer denies making a decision"
    attack_vector: "Claim decision was made by someone else"
    impact: MEDIUM
    likelihood: MEDIUM
    mitigations:
      - "Digital signatures on all decisions"
      - "Session and device binding"
      - "Timestamped audit records"
      - "Video/screen recording (optional)"
    detection:
      - "Signature verification"
      - "Session correlation"
      - "IP and device logging"
    
  - id: "T-REPUD-002"
    name: "Claim Submission Repudiation"
    category: REPUDIATION
    description: "Backend denies sending a claim event"
    attack_vector: "Claim event not attributed to source"
    impact: MEDIUM
    likelihood: LOW
    mitigations:
      - "Signed claim events"
      - "Correlation IDs tracking"
      - "Backend audit logging"
      - "Event sequence numbers"
    detection:
      - "Missing sequence numbers"
      - "Orphaned events"

  # ═══════════════════════════════════════════════════════════════════
  # INFORMATION DISCLOSURE THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-INFO-001"
    name: "PII Leakage"
    category: INFORMATION_DISCLOSURE
    description: "Member PII exposed through AI engine or logs"
    attack_vector: "Insufficient data sanitization, log exposure"
    impact: CRITICAL
    likelihood: MEDIUM
    mitigations:
      - "PII sanitization at source (backend)"
      - "Hash-based member identification"
      - "No PII in AI engine"
      - "Log scrubbing"
      - "Data classification enforcement"
    detection:
      - "PII scanning in logs"
      - "Data flow monitoring"
      - "DLP alerts"
    
  - id: "T-INFO-002"
    name: "Model Extraction"
    category: INFORMATION_DISCLOSURE
    description: "Attacker extracts fraud detection model"
    attack_vector: "Query probing to reverse-engineer model"
    impact: HIGH
    likelihood: LOW
    mitigations:
      - "Rate limiting on predictions"
      - "No raw model scores to external systems"
      - "Model obfuscation"
      - "Watermarking model outputs"
    detection:
      - "Unusual query patterns"
      - "High-volume inference requests"
      - "Sequential probing patterns"
    
  - id: "T-INFO-003"
    name: "Unauthorized Data Export"
    category: INFORMATION_DISCLOSURE
    description: "Admin exports sensitive data without authorization"
    attack_vector: "Abuse of export functionality"
    impact: HIGH
    likelihood: MEDIUM
    mitigations:
      - "Export requires supervisor approval"
      - "All exports logged with recipient"
      - "Data volume limits"
      - "Watermarking exported data"
      - "DLP on egress"
    detection:
      - "Unusual export volumes"
      - "After-hours exports"
      - "Export to unauthorized destinations"

  # ═══════════════════════════════════════════════════════════════════
  # DENIAL OF SERVICE THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-DOS-001"
    name: "AI Engine Overload"
    category: DENIAL_OF_SERVICE
    description: "Flood AI engine with claims to prevent processing"
    attack_vector: "High-volume claim submission"
    impact: MEDIUM
    likelihood: MEDIUM
    mitigations:
      - "Rate limiting at ingestion"
      - "Circuit breaker on AI engine"
      - "Backend continues without AI"
      - "Queue depth monitoring"
      - "Auto-scaling"
    detection:
      - "Queue depth alerts"
      - "Processing latency increase"
      - "Error rate spike"
    
  - id: "T-DOS-002"
    name: "Review Queue Flooding"
    category: DENIAL_OF_SERVICE
    description: "Overwhelm manual review queue"
    attack_vector: "Submit many claims designed to trigger review"
    impact: MEDIUM
    likelihood: MEDIUM
    mitigations:
      - "Queue depth limits"
      - "Auto-prioritization"
      - "Batch processing"
      - "SLA-based escalation"
    detection:
      - "Sudden queue growth"
      - "Pattern detection in queued claims"
    
  - id: "T-DOS-003"
    name: "Resource Exhaustion"
    category: DENIAL_OF_SERVICE
    description: "Exhaust compute/memory resources"
    attack_vector: "Complex claims, large payloads, memory leaks"
    impact: MEDIUM
    likelihood: LOW
    mitigations:
      - "Payload size limits"
      - "Processing timeouts"
      - "Resource quotas (K8s)"
      - "Memory limits"
      - "Graceful degradation"
    detection:
      - "Resource utilization alerts"
      - "OOM events"
      - "Timeout rate increase"

  # ═══════════════════════════════════════════════════════════════════
  # ELEVATION OF PRIVILEGE THREATS
  # ═══════════════════════════════════════════════════════════════════
  
  - id: "T-PRIV-001"
    name: "Unauthorized Admin Actions"
    category: ELEVATION_OF_PRIVILEGE
    description: "User performs actions beyond their role"
    attack_vector: "RBAC bypass, permission escalation"
    impact: HIGH
    likelihood: LOW
    mitigations:
      - "Server-side RBAC enforcement"
      - "Permission checks on every action"
      - "Least privilege principle"
      - "Regular permission audits"
    detection:
      - "Access denied events"
      - "Permission boundary violations"
      - "Role change alerts"
    
  - id: "T-PRIV-002"
    name: "Service Account Abuse"
    category: ELEVATION_OF_PRIVILEGE
    description: "Compromise service account for elevated access"
    attack_vector: "Stolen service credentials, container escape"
    impact: CRITICAL
    likelihood: LOW
    mitigations:
      - "Service account per component"
      - "Minimal permissions per account"
      - "Short-lived credentials"
      - "Secrets management (Vault)"
      - "Pod security policies"
    detection:
      - "Unusual API calls from service accounts"
      - "Credential usage anomalies"
      - "Container escape detection"
    
  - id: "T-PRIV-003"
    name: "Override Abuse"
    category: ELEVATION_OF_PRIVILEGE
    description: "Excessive use of rule/ML overrides"
    attack_vector: "Legitimate user abuses override capability"
    impact: HIGH
    likelihood: MEDIUM
    mitigations:
      - "Override quotas per user"
      - "Mandatory justification"
      - "Supervisor approval for major overrides"
      - "Override pattern monitoring"
      - "Regular override audits"
    detection:
      - "High override rate per user"
      - "Similar override patterns"
      - "Unusual override timing"
```

---

## 3. Authentication & Authorization

### 3.1 Service-to-Service Authentication

```python
class ServiceAuthenticator:
    """
    Handles mTLS and JWT authentication between services.
    """
    
    def __init__(self, config: AuthConfig):
        self.config = config
        self.cert_validator = CertificateValidator(config.ca_cert_path)
        self.jwt_validator = JWTValidator(config.jwt_public_key)
    
    async def authenticate_request(
        self,
        request: Request
    ) -> ServiceIdentity:
        """
        Authenticate incoming service request.
        Requires both mTLS and JWT.
        """
        # Step 1: Validate client certificate
        client_cert = request.transport.get_extra_info('ssl_object').getpeercert()
        if not client_cert:
            raise AuthenticationError("Client certificate required")
        
        cert_identity = self.cert_validator.validate(client_cert)
        if not cert_identity:
            raise AuthenticationError("Invalid client certificate")
        
        # Step 2: Validate JWT token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise AuthenticationError("JWT token required")
        
        token = auth_header[7:]
        jwt_claims = self.jwt_validator.validate(token)
        if not jwt_claims:
            raise AuthenticationError("Invalid JWT token")
        
        # Step 3: Verify certificate and JWT match
        if cert_identity.service_id != jwt_claims.get('sub'):
            raise AuthenticationError("Certificate and JWT mismatch")
        
        # Step 4: Check token expiry
        if jwt_claims.get('exp', 0) < time.time():
            raise AuthenticationError("Token expired")
        
        return ServiceIdentity(
            service_id=cert_identity.service_id,
            service_name=cert_identity.service_name,
            permissions=jwt_claims.get('permissions', []),
            authenticated_at=datetime.utcnow()
        )
    
    async def authenticate_message(
        self,
        message: bytes,
        signature: str,
        source_service: str
    ) -> bool:
        """
        Authenticate a signed message.
        """
        # Get expected signing key for source service
        signing_key = await self._get_service_signing_key(source_service)
        if not signing_key:
            return False
        
        # Verify signature
        expected_signature = hmac.new(
            signing_key,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)

class CertificateValidator:
    """
    Validates client certificates for mTLS.
    """
    
    def __init__(self, ca_cert_path: str):
        self.ca_cert = self._load_ca_cert(ca_cert_path)
        self.allowed_cns = {}  # Service ID -> allowed CN patterns
    
    def validate(self, peer_cert: dict) -> Optional[CertIdentity]:
        """Validate peer certificate."""
        try:
            # Check certificate chain
            if not self._verify_chain(peer_cert):
                return None
            
            # Check expiry
            not_after = peer_cert.get('notAfter')
            if self._is_expired(not_after):
                return None
            
            # Extract identity
            subject = dict(x[0] for x in peer_cert.get('subject', []))
            cn = subject.get('commonName')
            
            if not cn:
                return None
            
            # Parse service ID from CN
            service_id = self._parse_service_id(cn)
            
            # Verify CN is allowed
            if not self._is_allowed_cn(service_id, cn):
                return None
            
            return CertIdentity(
                service_id=service_id,
                service_name=cn,
                cert_serial=peer_cert.get('serialNumber'),
                valid_until=not_after
            )
            
        except Exception as e:
            logger.error(f"Certificate validation error: {e}")
            return None
```

### 3.2 User Authentication (Admin Portal)

```python
class AdminAuthenticator:
    """
    OIDC-based authentication with MFA for admin users.
    """
    
    def __init__(self, config: OIDCConfig):
        self.config = config
        self.oidc_client = OIDCClient(config)
        self.mfa_provider = MFAProvider(config.mfa_config)
        self.session_manager = SessionManager(config.session_config)
    
    async def authenticate(
        self,
        auth_code: str,
        redirect_uri: str,
        device_info: DeviceInfo
    ) -> AuthResult:
        """
        Authenticate user via OIDC flow.
        """
        # Step 1: Exchange auth code for tokens
        tokens = await self.oidc_client.exchange_code(auth_code, redirect_uri)
        if not tokens:
            return AuthResult(success=False, error="Invalid auth code")
        
        # Step 2: Validate ID token
        id_token_claims = await self.oidc_client.validate_id_token(tokens.id_token)
        if not id_token_claims:
            return AuthResult(success=False, error="Invalid ID token")
        
        # Step 3: Get user info
        user_info = await self.oidc_client.get_userinfo(tokens.access_token)
        
        # Step 4: Check MFA requirement
        user_id = id_token_claims.get('sub')
        if self._requires_mfa(user_id):
            if not id_token_claims.get('amr') or 'mfa' not in id_token_claims.get('amr', []):
                # MFA not completed, initiate MFA
                mfa_challenge = await self.mfa_provider.initiate_challenge(user_id)
                return AuthResult(
                    success=False,
                    requires_mfa=True,
                    mfa_challenge_id=mfa_challenge.challenge_id
                )
        
        # Step 5: Create session
        session = await self.session_manager.create_session(
            user_id=user_id,
            user_info=user_info,
            device_info=device_info,
            tokens=tokens
        )
        
        # Step 6: Log authentication
        await self._log_authentication(user_id, device_info, success=True)
        
        return AuthResult(
            success=True,
            session_id=session.session_id,
            user=User(
                user_id=user_id,
                email=user_info.get('email'),
                name=user_info.get('name'),
                role=await self._get_user_role(user_id)
            )
        )
    
    async def verify_mfa(
        self,
        challenge_id: str,
        mfa_code: str,
        device_info: DeviceInfo
    ) -> AuthResult:
        """Verify MFA code."""
        # Verify MFA
        verification = await self.mfa_provider.verify_challenge(
            challenge_id,
            mfa_code
        )
        
        if not verification.success:
            await self._log_mfa_failure(challenge_id, device_info)
            return AuthResult(success=False, error="Invalid MFA code")
        
        # Create session
        user_id = verification.user_id
        session = await self.session_manager.create_session(
            user_id=user_id,
            user_info=await self.oidc_client.get_cached_userinfo(user_id),
            device_info=device_info,
            mfa_verified=True
        )
        
        return AuthResult(
            success=True,
            session_id=session.session_id,
            user=User(
                user_id=user_id,
                role=await self._get_user_role(user_id)
            )
        )
```

### 3.3 Authorization Enforcement

```python
class AuthorizationEnforcer:
    """
    Enforces RBAC and resource-level permissions.
    """
    
    def __init__(self, config: AuthzConfig):
        self.config = config
        self.permission_store = PermissionStore(config.permission_db)
    
    async def authorize(
        self,
        user: User,
        action: str,
        resource_type: str,
        resource_id: str = None
    ) -> AuthzResult:
        """
        Check if user is authorized for action.
        """
        # Get user permissions
        permissions = await self.permission_store.get_permissions(
            user.user_id,
            user.role
        )
        
        # Check action permission
        if not self._has_action_permission(permissions, action, resource_type):
            return AuthzResult(
                authorized=False,
                reason=f"User {user.user_id} lacks permission for {action} on {resource_type}"
            )
        
        # Check resource-level permission if applicable
        if resource_id:
            if not await self._has_resource_permission(user, action, resource_type, resource_id):
                return AuthzResult(
                    authorized=False,
                    reason=f"User {user.user_id} lacks permission for resource {resource_id}"
                )
        
        # Check additional constraints
        constraints = await self._get_constraints(user, action, resource_type)
        constraint_check = await self._check_constraints(constraints, user, resource_id)
        
        if not constraint_check.passed:
            return AuthzResult(
                authorized=False,
                reason=constraint_check.reason
            )
        
        return AuthzResult(authorized=True)
    
    def _has_action_permission(
        self,
        permissions: List[Permission],
        action: str,
        resource_type: str
    ) -> bool:
        """Check if permissions include action on resource type."""
        for perm in permissions:
            if perm.action == action and perm.resource_type in (resource_type, '*'):
                return True
            if perm.action == '*' and perm.resource_type in (resource_type, '*'):
                return True
        return False
    
    async def _check_constraints(
        self,
        constraints: List[Constraint],
        user: User,
        resource_id: str
    ) -> ConstraintResult:
        """Check additional authorization constraints."""
        for constraint in constraints:
            if constraint.type == 'AMOUNT_LIMIT':
                # Check amount doesn't exceed user's limit
                amount = await self._get_resource_amount(resource_id)
                if amount > constraint.value:
                    return ConstraintResult(
                        passed=False,
                        reason=f"Amount {amount} exceeds limit {constraint.value}"
                    )
            
            elif constraint.type == 'QUEUE_ACCESS':
                # Check user can access queue
                queue = await self._get_resource_queue(resource_id)
                if queue not in constraint.allowed_values:
                    return ConstraintResult(
                        passed=False,
                        reason=f"User cannot access queue {queue}"
                    )
            
            elif constraint.type == 'TIME_WINDOW':
                # Check within allowed time window
                if not self._within_time_window(constraint):
                    return ConstraintResult(
                        passed=False,
                        reason="Action not allowed at this time"
                    )
        
        return ConstraintResult(passed=True)
```

---

## 4. Data Protection

### 4.1 Encryption Standards

```yaml
encryption:
  at_rest:
    algorithm: AES-256-GCM
    key_management: AWS KMS / HashiCorp Vault
    key_rotation: 90 days
    
    databases:
      - PostgreSQL: TDE with customer-managed keys
      - ChromaDB: Filesystem encryption
      - Redis: Encrypted storage
    
    storage:
      - S3: SSE-KMS
      - EBS: AES-256
      - Audit logs: Write-once with encryption
  
  in_transit:
    protocol: TLS 1.3
    cipher_suites:
      - TLS_AES_256_GCM_SHA384
      - TLS_CHACHA20_POLY1305_SHA256
    certificate_type: RSA-4096 or ECDSA-P384
    certificate_validity: 1 year
    
    mutual_tls:
      required: true
      ca: Internal PKI
      client_cert_validation: strict
  
  sensitive_fields:
    member_id:
      type: SHA-256 hash
      salt: per-environment
    
    claim_amounts:
      type: AES-256-GCM
      key_scope: per-claim
    
    reviewer_notes:
      type: AES-256-GCM
      key_scope: per-review
```

### 4.2 Data Masking Rules

```python
class DataMasker:
    """
    Masks sensitive data for logging and display.
    """
    
    MASKING_RULES = {
        'member_id': lambda x: f"M-*****{x[-4:]}",
        'policy_id': lambda x: f"POL-*****{x[-4:]}",
        'provider_id': lambda x: f"PRV-*****{x[-4:]}",
        'ssn': lambda x: "***-**-****",
        'email': lambda x: f"{x[0]}***@{x.split('@')[1]}",
        'phone': lambda x: f"***-***-{x[-4:]}",
        'claim_id': lambda x: x,  # No masking needed
        'amount': lambda x: x,    # No masking needed
    }
    
    def mask_for_logging(self, data: dict) -> dict:
        """Mask sensitive fields for logging."""
        masked = {}
        for key, value in data.items():
            if key in self.MASKING_RULES:
                masked[key] = self.MASKING_RULES[key](str(value))
            elif self._is_pii_field(key):
                masked[key] = "[REDACTED]"
            else:
                masked[key] = value
        return masked
    
    def mask_for_display(self, data: dict, user_role: str) -> dict:
        """Mask data based on user role."""
        if user_role in ('COMPLIANCE_OFFICER', 'FRAUD_DIRECTOR'):
            # Full access
            return data
        
        masked = {}
        for key, value in data.items():
            if key in self.MASKING_RULES:
                masked[key] = self.MASKING_RULES[key](str(value))
            else:
                masked[key] = value
        return masked
```

---

## 5. Audit Logging

### 5.1 Audit Event Structure

```python
@dataclass
class AuditEvent:
    """
    Immutable audit event structure.
    """
    # Event identification
    event_id: str               # UUID
    event_type: str             # From AuditEventType enum
    event_category: str         # SECURITY, BUSINESS, SYSTEM
    
    # Timestamp
    timestamp: datetime
    timezone: str = "UTC"
    
    # Actor information
    actor_type: str             # USER, SERVICE, SYSTEM
    actor_id: str
    actor_role: Optional[str]
    actor_ip: Optional[str]
    actor_user_agent: Optional[str]
    session_id: Optional[str]
    
    # Action details
    action: str                 # CREATE, READ, UPDATE, DELETE, EXECUTE
    resource_type: str
    resource_id: str
    
    # Context
    request_id: str             # Correlation ID
    previous_state: Optional[dict]
    new_state: Optional[dict]
    change_summary: Optional[str]
    
    # Security context
    authentication_method: str   # mTLS, JWT, OIDC
    authorization_decision: str  # ALLOW, DENY
    
    # Integrity
    sequence_number: int
    previous_hash: str
    event_hash: str
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of event."""
        content = json.dumps({
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'actor_id': self.actor_id,
            'action': self.action,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'previous_hash': self.previous_hash,
            'sequence_number': self.sequence_number
        }, sort_keys=True)
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
```

### 5.2 Audit Logger Implementation

```python
class ImmutableAuditLogger:
    """
    Append-only audit logger with cryptographic chaining.
    """
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.db = self._connect_db(config.database)
        self.siem_client = SIEMClient(config.siem)
        self.sequence_counter = AtomicCounter()
        self._last_hash = self._get_last_hash()
    
    async def log_event(
        self,
        event_type: str,
        actor: Actor,
        action: str,
        resource_type: str,
        resource_id: str,
        context: dict = None
    ) -> str:
        """
        Log an audit event. Returns event ID.
        """
        # Generate event
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            event_category=self._categorize_event(event_type),
            timestamp=datetime.utcnow(),
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            actor_ip=actor.ip_address,
            actor_user_agent=actor.user_agent,
            session_id=actor.session_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=context.get('request_id') if context else None,
            previous_state=context.get('previous_state') if context else None,
            new_state=context.get('new_state') if context else None,
            change_summary=context.get('change_summary') if context else None,
            authentication_method=actor.auth_method,
            authorization_decision=context.get('authz_decision', 'ALLOW') if context else 'ALLOW',
            sequence_number=self.sequence_counter.increment(),
            previous_hash=self._last_hash,
            event_hash=""
        )
        
        # Compute hash
        event.event_hash = event.compute_hash()
        self._last_hash = event.event_hash
        
        # Store in database (atomic)
        await self._store_event(event)
        
        # Forward to SIEM (async)
        asyncio.create_task(self._forward_to_siem(event))
        
        return event.event_id
    
    async def _store_event(self, event: AuditEvent) -> None:
        """Store event in append-only table."""
        await self.db.execute("""
            INSERT INTO audit_log (
                event_id, event_type, event_category,
                timestamp, actor_type, actor_id, actor_role,
                actor_ip, session_id, action,
                resource_type, resource_id, request_id,
                previous_state, new_state, change_summary,
                authentication_method, authorization_decision,
                sequence_number, previous_hash, event_hash
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
        """, *event.__dict__.values())
    
    async def verify_chain(
        self,
        start_sequence: int = 0,
        end_sequence: int = None
    ) -> ChainVerificationResult:
        """Verify integrity of audit chain."""
        events = await self.db.fetch("""
            SELECT * FROM audit_log
            WHERE sequence_number >= $1
            ORDER BY sequence_number ASC
        """, start_sequence)
        
        if end_sequence:
            events = [e for e in events if e['sequence_number'] <= end_sequence]
        
        errors = []
        previous_hash = events[0]['previous_hash'] if events else None
        
        for event in events:
            # Verify hash chain
            if event['previous_hash'] != previous_hash:
                errors.append({
                    'sequence': event['sequence_number'],
                    'error': 'Chain broken',
                    'expected_previous': previous_hash,
                    'actual_previous': event['previous_hash']
                })
            
            # Verify event hash
            computed_hash = self._compute_event_hash(event)
            if computed_hash != event['event_hash']:
                errors.append({
                    'sequence': event['sequence_number'],
                    'error': 'Hash mismatch',
                    'computed': computed_hash,
                    'stored': event['event_hash']
                })
            
            previous_hash = event['event_hash']
        
        return ChainVerificationResult(
            verified_events=len(events),
            errors=errors,
            chain_valid=len(errors) == 0,
            verification_time=datetime.utcnow()
        )
```

### 5.3 Audit Retention Policy

```yaml
audit_retention:
  # Hot storage (fast query)
  hot_tier:
    duration: 90 days
    storage: PostgreSQL
    access: Online
    
  # Warm storage (archived)
  warm_tier:
    duration: 2 years
    storage: S3 Glacier Instant Retrieval
    access: Minutes
    
  # Cold storage (compliance)
  cold_tier:
    duration: 7 years
    storage: S3 Glacier Deep Archive
    access: Hours
    
  # Legal hold
  legal_hold:
    enabled: true
    prevents_deletion: true
    requires_approval: COMPLIANCE_OFFICER
    
  # Immutability
  immutability:
    s3_object_lock: true
    governance_mode: true
    retention_period: 7 years
```

---

## 6. Security Monitoring

### 6.1 Security Alerts

```python
class SecurityAlertManager:
    """
    Manages security alerts and incident response.
    """
    
    ALERT_DEFINITIONS = {
        'AUTH_FAILED_MULTIPLE': {
            'threshold': 5,
            'window_minutes': 10,
            'severity': 'HIGH',
            'action': 'LOCK_ACCOUNT'
        },
        'UNUSUAL_LOGIN_LOCATION': {
            'severity': 'MEDIUM',
            'action': 'NOTIFY_USER'
        },
        'MASS_DATA_EXPORT': {
            'threshold_mb': 100,
            'severity': 'HIGH',
            'action': 'NOTIFY_SUPERVISOR'
        },
        'PRIVILEGE_ESCALATION': {
            'severity': 'CRITICAL',
            'action': 'IMMEDIATE_LOCKDOWN'
        },
        'SIGNATURE_FAILURE': {
            'severity': 'CRITICAL',
            'action': 'REJECT_AND_ALERT'
        },
        'CHAIN_INTEGRITY_FAILURE': {
            'severity': 'CRITICAL',
            'action': 'HALT_AND_INVESTIGATE'
        }
    }
    
    async def check_and_alert(
        self,
        event_type: str,
        context: dict
    ) -> Optional[SecurityAlert]:
        """Check if event triggers a security alert."""
        
        if event_type == 'LOGIN_FAILED':
            return await self._check_failed_login_pattern(context)
        
        elif event_type == 'LOGIN':
            return await self._check_unusual_login(context)
        
        elif event_type == 'DATA_EXPORT':
            return await self._check_mass_export(context)
        
        elif event_type == 'PERMISSION_CHANGE':
            return await self._check_privilege_escalation(context)
        
        elif event_type == 'SIGNATURE_INVALID':
            return await self._create_critical_alert(
                'SIGNATURE_FAILURE',
                context
            )
        
        return None
    
    async def _check_failed_login_pattern(
        self,
        context: dict
    ) -> Optional[SecurityAlert]:
        """Check for brute force login attempts."""
        user_id = context.get('user_id')
        ip_address = context.get('ip_address')
        
        # Count recent failures
        recent_failures = await self.db.fetch("""
            SELECT COUNT(*) FROM audit_log
            WHERE event_type = 'LOGIN_FAILED'
            AND (actor_id = $1 OR actor_ip = $2)
            AND timestamp > NOW() - INTERVAL '10 minutes'
        """, user_id, ip_address)
        
        count = recent_failures[0]['count']
        threshold = self.ALERT_DEFINITIONS['AUTH_FAILED_MULTIPLE']['threshold']
        
        if count >= threshold:
            # Lock account
            await self._lock_account(user_id)
            
            return SecurityAlert(
                alert_type='AUTH_FAILED_MULTIPLE',
                severity='HIGH',
                title=f"Multiple failed login attempts for {user_id}",
                description=f"{count} failed attempts in 10 minutes",
                context={
                    'user_id': user_id,
                    'ip_address': ip_address,
                    'failure_count': count,
                    'action_taken': 'Account locked'
                },
                timestamp=datetime.utcnow()
            )
        
        return None
```

---

**END OF SECURITY THREAT MODEL & AUDIT SPECIFICATION**


