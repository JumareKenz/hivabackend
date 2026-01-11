#!/usr/bin/env python3
"""
Quick validation test for port 8300 configuration
Tests that all services are correctly configured for port 8300
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def test_config():
    """Test configuration settings"""
    print("🔍 Testing Configuration...")
    
    from src.core.config import settings
    
    assert settings.ADMIN_PORTAL_PORT == 8300, f"ADMIN_PORTAL_PORT is {settings.ADMIN_PORTAL_PORT}, expected 8300"
    assert settings.API_PORT == 8300, f"API_PORT is {settings.API_PORT}, expected 8300"
    
    print(f"✅ ADMIN_PORTAL_PORT: {settings.ADMIN_PORTAL_PORT}")
    print(f"✅ API_PORT: {settings.API_PORT}")
    print(f"✅ API_HOST: {settings.API_HOST}")
    print()

def test_imports():
    """Test that all components import correctly"""
    print("🔍 Testing Component Imports...")
    
    try:
        from src.core.models import ClaimData
        print("✅ Core models imported")
        
        from src.rule_engine.engine import rule_engine
        print("✅ Rule engine imported")
        
        from src.ml_engine.engine import ml_engine
        print("✅ ML engine imported")
        
        from src.decision_engine.synthesis import decision_engine
        print("✅ Decision engine imported")
        
        from src.audit.audit_logger import audit_logger
        print("✅ Audit logger imported")
        
        from src.events.kafka_consumer import ClaimsKafkaConsumer
        print("✅ Kafka consumer imported")
        
        from src.orchestrator import orchestrator
        print("✅ Orchestrator imported")
        
        from src.api.main import app
        print("✅ FastAPI app imported")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_api_structure():
    """Test API structure"""
    print("🔍 Testing API Structure...")
    
    try:
        from src.api.main import app
        
        routes = [route.path for route in app.routes]
        
        expected_routes = [
            "/",
            "/health",
            "/api/info"
        ]
        
        for route in expected_routes:
            if route in routes:
                print(f"✅ Route found: {route}")
            else:
                print(f"⚠️  Route missing: {route}")
        
        print(f"📊 Total routes: {len(routes)}")
        print()
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("DCAL PORT 8300 CONFIGURATION TEST")
    print("="*60)
    print()
    
    all_passed = True
    
    # Test 1: Configuration
    try:
        test_config()
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        all_passed = False
    
    # Test 2: Imports
    try:
        if not test_imports():
            all_passed = False
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        all_passed = False
    
    # Test 3: API Structure
    try:
        if not test_api_structure():
            all_passed = False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        all_passed = False
    
    # Summary
    print("="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("System is ready to run on port 8300")
        print()
        print("To start the server:")
        print("  ./start_api.sh")
        print()
        print("Or manually:")
        print("  uvicorn src.api.main:app --host 0.0.0.0 --port 8300")
        print()
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Please check the errors above and fix configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

