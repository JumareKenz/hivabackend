#!/usr/bin/env python3
"""
Verify Clinical PPH routes are properly registered
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from app.main import app
    
    print("=" * 70)
    print("CLINICAL PPH ROUTES VERIFICATION")
    print("=" * 70)
    
    # Get all routes
    all_routes = []
    for route in app.routes:
        if hasattr(route, 'path'):
            methods = getattr(route, 'methods', set())
            if methods:
                all_routes.append((route.path, methods))
    
    # Find clinical PPH routes
    clinical_routes = [(path, methods) for path, methods in all_routes if 'clinical' in path.lower()]
    
    print(f"\n📋 Found {len(clinical_routes)} Clinical PPH route(s):\n")
    for path, methods in sorted(clinical_routes):
        methods_str = ', '.join(sorted(methods))
        print(f"   {methods_str:20} {path}")
    
    # Check if routes exist
    expected_routes = [
        '/api/v1/clinical-pph/ask',
        '/api/v1/clinical-pph/stream',
        '/api/v1/clinical-pph/health',
    ]
    
    print(f"\n✅ Expected routes:")
    for expected in expected_routes:
        found = any(expected in path for path, _ in clinical_routes)
        status = "✓" if found else "✗"
        print(f"   {status} {expected}")
    
    # Check router import
    print(f"\n🔍 Router Import Check:")
    try:
        from app.api.v1.clinical_pph import router
        print(f"   ✓ Router imports successfully")
        print(f"   ✓ Router prefix: {router.prefix}")
        print(f"   ✓ Router tags: {router.tags}")
    except Exception as e:
        print(f"   ✗ Router import failed: {e}")
    
    # Check main.py registration
    print(f"\n🔍 Main.py Registration Check:")
    try:
        with open('app/main.py', 'r') as f:
            content = f.read()
            if 'clinical_pph_router' in content:
                print(f"   ✓ Router imported in main.py")
            else:
                print(f"   ✗ Router not found in main.py")
            if 'app.include_router(clinical_pph_router' in content:
                print(f"   ✓ Router registered in main.py")
            else:
                print(f"   ✗ Router not registered in main.py")
    except Exception as e:
        print(f"   ✗ Error checking main.py: {e}")
    
    print("\n" + "=" * 70)
    
    if len(clinical_routes) >= 3:
        print("✅ ALL ROUTES PROPERLY REGISTERED")
        print("\n⚠️  If endpoints are not accessible, the server needs to be restarted:")
        print("   1. Stop the current server (Ctrl+C or kill process)")
        print("   2. Restart: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print("\n   Or for production:")
        print("   - Restart the service/systemd unit")
        print("   - Redeploy if using containers")
    else:
        print("❌ ROUTES NOT FOUND - Check configuration")
    
    print("=" * 70)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


