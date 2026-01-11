#!/usr/bin/env python3
"""
Generate a test JWT bearer token for DCAL API testing
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import jwt

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from src.core.config import settings


def generate_test_token(username: str = "testuser", roles: list = None, user_id: str = None):
    """Generate a test JWT token"""
    
    if roles is None:
        roles = ["reviewer", "admin"]  # Default roles with full access
    
    if user_id is None:
        user_id = f"user_{username}"
    
    # Token expiration (default 30 minutes, but we'll make it 24 hours for testing)
    expire = datetime.utcnow() + timedelta(hours=24)
    
    # Create token payload
    payload = {
        "user_id": user_id,
        "username": username,
        "roles": roles,
        "exp": expire
    }
    
    # Encode token
    try:
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return token
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        return None


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate JWT test token for DCAL API")
    parser.add_argument("--username", default="testuser", help="Username for token")
    parser.add_argument("--roles", nargs="+", default=["reviewer", "admin"], 
                       help="Roles for token (default: reviewer admin)")
    parser.add_argument("--user-id", help="User ID (default: user_<username>)")
    parser.add_argument("--format", choices=["token", "curl", "header", "full"], 
                       default="full", help="Output format")
    
    args = parser.parse_args()
    
    print("🔐 Generating JWT Bearer Token for DCAL API")
    print("=" * 80)
    print()
    
    # Generate token
    token = generate_test_token(
        username=args.username,
        roles=args.roles,
        user_id=args.user_id
    )
    
    if not token:
        print("❌ Failed to generate token")
        sys.exit(1)
    
    # Output based on format
    if args.format == "token":
        print(token)
    elif args.format == "curl":
        print(f'curl -H "Authorization: Bearer {token}" http://localhost:8300/api/claims/process')
    elif args.format == "header":
        print(f"Authorization: Bearer {token}")
    else:  # full
        print("✅ Token Generated Successfully!")
        print()
        print("Token Details:")
        print(f"  Username: {args.username}")
        print(f"  Roles: {', '.join(args.roles)}")
        print(f"  Expires: 24 hours from now")
        print()
        print("=" * 80)
        print("BEARER TOKEN:")
        print("=" * 80)
        print(token)
        print()
        print("=" * 80)
        print("USAGE EXAMPLES:")
        print("=" * 80)
        print()
        print("1. curl with Bearer token:")
        print(f'   curl -X POST http://localhost:8300/api/claims/process \\')
        print(f'     -H "Content-Type: application/json" \\')
        print(f'     -H "Authorization: Bearer {token[:50]}..." \\')
        print(f'     -d \'{{"claim_id": "TEST-001", ...}}\'')
        print()
        print("2. In Swagger UI (http://localhost:8300/docs):")
        print("   - Click the 'Authorize' button (🔒) at the top")
        print("   - Enter: Bearer <token>")
        print("   - Or just: <token> (Swagger adds 'Bearer' prefix)")
        print()
        print("3. Python requests:")
        print("   import requests")
        print("   headers = {'Authorization': f'Bearer {token}'}")
        print("   response = requests.post(url, headers=headers, json=data)")
        print()
        print("4. JavaScript/fetch:")
        print("   fetch(url, {")
        print("     headers: {")
        print(f"       'Authorization': 'Bearer {token[:50]}...'")
        print("     }")
        print("   })")
        print()
        print("=" * 80)
        print("QUICK COPY:")
        print("=" * 80)
        print(f"Bearer {token}")
        print()
        print("=" * 80)
        print("⚠️  NOTE: This is a TEST token. For production, use proper authentication.")
        print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
