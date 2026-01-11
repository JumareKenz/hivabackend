"""
Test Admin Chat API Endpoint with Vanna AI
"""
import requests
import json
import sys
from pathlib import Path

# Load API key from environment or config
sys.path.insert(0, str(Path(__file__).parent))
from app.core.config import settings
import os

API_KEY = os.getenv('ADMIN_API_KEY') or settings.ADMIN_API_KEY
BASE_URL = f"http://localhost:{settings.PORT}"


def test_endpoint():
    """Test the admin query endpoint"""
    print("🧪 Testing Admin Chat API Endpoint with Vanna AI\n")
    print(f"📍 Base URL: {BASE_URL}\n")
    
    if not API_KEY:
        print("❌ ADMIN_API_KEY not set")
        return
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Test queries
    test_queries = [
        {
            "query": "show me claims by status",
            "description": "Simple aggregation query"
        },
        {
            "query": "how many claims are there",
            "description": "Count query"
        }
    ]
    
    print("=" * 70)
    
    for i, test in enumerate(test_queries, 1):
        print(f"\n📝 Test {i}: {test['description']}")
        print(f"   Query: {test['query']}")
        print("-" * 70)
        
        payload = {
            "query": test['query'],
            "session_id": f"test_session_{i}"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/admin/query",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            print(f"✅ Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if Vanna was used
                sql_source = "unknown"
                if 'sql' in data:
                    # Check response for source indicator
                    sql = data.get('sql', '')
                    print(f"✅ SQL Generated:\n{sql[:200]}...")
                
                # Check confidence
                confidence = data.get('confidence', 0)
                print(f"✅ Confidence: {confidence:.2f}")
                
                # Check row count
                row_count = data.get('row_count', 0)
                print(f"✅ Rows Returned: {row_count}")
                
                # Check if visualization was created
                if 'visualization' in data:
                    viz_type = data['visualization'].get('type', 'unknown')
                    print(f"✅ Visualization Type: {viz_type}")
                
                # Check summary
                if 'summary' in data:
                    summary = data['summary'][:100] if data['summary'] else "N/A"
                    print(f"✅ Summary: {summary}...")
                
                # Try to determine if Vanna was used
                # (Vanna typically has higher confidence and better SQL structure)
                if confidence >= 0.85:
                    print(f"✅ Likely using Vanna AI (high confidence: {confidence:.2f})")
                else:
                    print(f"ℹ️  Using legacy generator (confidence: {confidence:.2f})")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection Error: Is the service running on port {settings.PORT}?")
        except requests.exceptions.Timeout:
            print(f"❌ Timeout: Request took too long")
        except Exception as e:
            print(f"❌ Error: {str(e)[:200]}")
        
        print("-" * 70)
    
    print("\n" + "=" * 70)
    print("✅ Endpoint testing complete!")
    
    # Test health endpoint
    print("\n🏥 Testing Health Endpoint...")
    try:
        health_response = requests.get(
            f"{BASE_URL}/health",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10
        )
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ Health Status: {health_data}")
        else:
            print(f"⚠️  Health check returned: {health_response.status_code}")
    except Exception as e:
        print(f"⚠️  Health check error: {str(e)[:100]}")


if __name__ == "__main__":
    test_endpoint()




