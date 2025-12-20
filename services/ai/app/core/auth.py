"""
Authentication and Authorization Service for Admin Features
"""
import os
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import hashlib
import hmac


class AdminAuthService:
    """Handles admin authentication and authorization"""
    
    def __init__(self):
        # Get admin API key from settings (which loads from .env)
        from app.core.config import settings
        self.admin_api_key = settings.ADMIN_API_KEY or ""
        self.admin_tokens: dict[str, dict] = {}  # token -> {user_id, expires_at, role}
        self.token_ttl_hours = 24
        
        # If no API key set, generate a warning (should be set in production)
        if not self.admin_api_key:
            print("⚠️  WARNING: ADMIN_API_KEY not set. Admin features will be disabled.")
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify admin API key"""
        if not self.admin_api_key:
            return False
        return hmac.compare_digest(api_key, self.admin_api_key)
    
    def generate_token(self, user_id: str, role: str = "admin") -> str:
        """Generate a temporary admin token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=self.token_ttl_hours)
        
        self.admin_tokens[token] = {
            "user_id": user_id,
            "role": role,
            "expires_at": expires_at,
            "created_at": datetime.now()
        }
        
        return token
    
    def verify_token(self, token: str) -> dict:
        """Verify admin token and return user info"""
        if token not in self.admin_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        token_data = self.admin_tokens[token]
        
        # Check expiration
        if datetime.now() > token_data["expires_at"]:
            del self.admin_tokens[token]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        
        return token_data
    
    def require_admin(self, credentials: HTTPAuthorizationCredentials = Security(HTTPBearer())) -> dict:
        """Dependency to require admin authentication"""
        token = credentials.credentials
        
        # First try token-based auth
        try:
            return self.verify_token(token)
        except HTTPException:
            pass
        
        # Fallback to API key auth
        if self.verify_api_key(token):
            return {"user_id": "admin", "role": "admin"}
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens (call periodically)"""
        now = datetime.now()
        expired = [
            token for token, data in self.admin_tokens.items()
            if now > data["expires_at"]
        ]
        for token in expired:
            del self.admin_tokens[token]


# Global instance
admin_auth = AdminAuthService()

