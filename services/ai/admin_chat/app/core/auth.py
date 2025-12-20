"""
Admin Authentication Service
"""
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from typing import Dict, Any, Optional
from app.core.config import settings


# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class AdminAuth:
    """Admin authentication service"""
    
    def __init__(self):
        self.admin_api_key = settings.ADMIN_API_KEY
    
    def _validate_api_key(self, api_key: Optional[str]) -> bool:
        """Validate API key"""
        if not self.admin_api_key:
            # If no API key is set, allow access (development mode)
            return True
        
        return api_key == self.admin_api_key
    
    def _validate_bearer_token(self, credentials: Optional[HTTPAuthorizationCredentials]) -> bool:
        """Validate bearer token (can be extended for JWT or other tokens)"""
        if not credentials:
            return False
        
        # For now, treat bearer token as API key
        # Can be extended to validate JWT tokens
        return self._validate_api_key(credentials.credentials)
    
    async def require_admin(
        self,
        api_key: Optional[str] = Security(api_key_header),
        credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
    ) -> Dict[str, Any]:
        """
        Dependency to require admin authentication
        
        Accepts either:
        - X-API-Key header
        - Bearer token in Authorization header
        """
        # Try API key first
        if api_key and self._validate_api_key(api_key):
            return {
                "user_id": "admin",
                "auth_method": "api_key",
                "authenticated": True
            }
        
        # Try bearer token
        if credentials and self._validate_bearer_token(credentials):
            return {
                "user_id": "admin",
                "auth_method": "bearer",
                "authenticated": True
            }
        
        # No valid authentication
        if not self.admin_api_key:
            # Development mode: allow access if no API key is configured
            return {
                "user_id": "admin",
                "auth_method": "none",
                "authenticated": True
            }
        
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin API key. Provide X-API-Key header or Bearer token."
        )


# Global instance
admin_auth = AdminAuth()







