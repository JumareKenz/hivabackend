"""
Authentication and Authorization
JWT-based auth with RBAC
"""

import jwt
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from ..core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()


class User(BaseModel):
    """User model"""
    user_id: str
    username: str
    email: str
    roles: List[str]
    full_name: Optional[str] = None


class TokenData(BaseModel):
    """JWT token data"""
    user_id: str
    username: str
    roles: List[str]
    exp: datetime


def create_access_token(user: User) -> str:
    """Create JWT access token"""
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "user_id": user.user_id,
        "username": user.username,
        "roles": user.roles,
        "exp": expire
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> TokenData:
    """
    Verify JWT token.
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        token_data = TokenData(
            user_id=payload["user_id"],
            username=payload["username"],
            roles=payload.get("roles", []),
            exp=datetime.fromtimestamp(payload["exp"])
        )
        
        # Check expiration
        if token_data.exp < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        
        return token_data
        
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )


async def get_current_user(token_data: TokenData = Depends(verify_token)) -> User:
    """Get current authenticated user"""
    return User(
        user_id=token_data.user_id,
        username=token_data.username,
        email=f"{token_data.username}@example.com",  # Placeholder
        roles=token_data.roles
    )


def require_role(required_roles: List[str]):
    """
    Dependency to require specific roles.
    
    Usage:
        @app.get("/admin", dependencies=[Depends(require_role(["admin"]))])
    """
    async def role_checker(user: User = Depends(get_current_user)):
        if not any(role in user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {required_roles}"
            )
        return user
    
    return role_checker


# Role definitions
class Roles:
    """Standard role definitions"""
    ADMIN = "admin"
    SENIOR_REVIEWER = "senior_reviewer"
    REVIEWER = "reviewer"
    FRAUD_INVESTIGATOR = "fraud_investigator"
    MEDICAL_DIRECTOR = "medical_director"
    COMPLIANCE_OFFICER = "compliance_officer"
    READ_ONLY = "read_only"


