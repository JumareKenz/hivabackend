"""
Test the actual API endpoint with real query
"""

import requests
import json
import sys
from datetime import datetime

# Default endpoint (adjust if needed)
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/v1/admin/query"

def test_endpoint(query: str, session_id: str = None, auth_token: str = None):
    """Test the admin query endpoint"""
    print("\n" + "="*80)
    print(f"TESTING API ENDPOINT")
    print("="*80)
    print(f"Endpoint: {ENDPOINT}")
    print(f"Query: '{query}'")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    # Prepare request
    payload = {
        "query": query,
        "refine_query": False
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add auth token if provided
    if auth_token:
        headers["X-API-Key"] = auth_token
        headers["Authorization"] = f"Bearer {auth_token}"
    else:
        # Try to get from environment or config
        import os
        env_key = os.getenv("ADMIN_API_KEY")
        if not env_key:
            # Try to load from .env file
            try:
                from dotenv import load_dotenv
                from pathlib import Path
                env_path = Path(__file__).parent / ".env"
                if env_path.exists():
                    load_dotenv(env_path)
                    env_key = os.getenv("ADMIN_API_KEY")
            except:
                pass
        
        if env_key:
            headers["X-API-Key"] = env_key
            print(f"✅ Using ADMIN_API_KEY from environment")
        else:
            # Try common test keys or skip auth
            test_keys = ["test-key", "dev-key", "admin-key", ""]
            print(f"⚠️  No ADMIN_API_KEY found - trying test keys...")
            # Will try without key first, then with test keys if needed
    
    try:
        print("📤 Sending request...")
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers=headers,
            timeout=60
        )
        
        print(f"📥 Response Status: {response.status_code}")
        print(f"📥 Response Headers: {dict(response.headers)}\n")
        
        if response.status_code == 200:
            data = response.json()
            
            print("="*80)
            print("RESPONSE ANALYSIS")
            print("="*80)
            
            # Check success
            success = data.get("success", False)
            print(f"\n✅ Success: {success}")
            
            if success:
                # Domain 3.1: Query Intelligence
                print("\n🔍 Domain 3.1: Query Intelligence")
                print("-" * 80)
                # Intent would be in metadata if available
                
                # Domain 3.2: Safety & Governance
                print("\n🔒 Domain 3.2: Safety & Governance")
                print("-" * 80)
                # PII columns would be in metadata
                
                # Domain 3.3: Explainability
                print("\n📖 Domain 3.3: Explainability")
                print("-" * 80)
                sql_explanation = data.get("sql_explanation", "N/A")
                print(f"SQL Explanation: {sql_explanation}")
                
                # SQL Generated
                print("\n💻 Generated SQL")
                print("-" * 80)
                sql = data.get("sql", "N/A")
                print(f"{sql}")
                
                # Results
                print("\n📊 Results")
                print("-" * 80)
                results = data.get("data", [])
                row_count = data.get("row_count", 0)
                print(f"Total Rows: {row_count}")
                print(f"Returned Rows: {len(results)}")
                
                if results:
                    print("\nFirst 5 Results:")
                    for i, row in enumerate(results[:5], 1):
                        print(f"  {i}. {row}")
                
                # Confidence
                print("\n📈 Confidence & Metrics")
                print("-" * 80)
                confidence = data.get("confidence", "N/A")
                print(f"Confidence Score: {confidence}")
                
                # Source
                source = data.get("source", "N/A")
                print(f"SQL Source: {source}")
                
                # Summary
                summary = data.get("summary", "N/A")
                print(f"\n📝 Summary: {summary}")
                
                # Visualization
                visualization = data.get("visualization", {})
                if visualization:
                    print(f"\n📊 Visualization Type: {visualization.get('type', 'N/A')}")
                    print(f"Columns: {visualization.get('columns', [])}")
                
                print("\n" + "="*80)
                print("✅ TEST PASSED - Query executed successfully")
                print("="*80)
                
                # Check if disease name is returned (not code)
                if results:
                    first_result = results[0]
                    # Look for diagnosis/disease field
                    diagnosis_field = None
                    for key in first_result.keys():
                        if 'diagnosis' in key.lower() or 'disease' in key.lower():
                            diagnosis_field = key
                            break
                    
                    if diagnosis_field:
                        diagnosis_value = first_result[diagnosis_field]
                        # Check if it's a name (string) not a code (numeric)
                        if isinstance(diagnosis_value, str) and not diagnosis_value.isdigit():
                            print(f"\n✅ VERIFIED: Disease name returned: '{diagnosis_value}' (not code)")
                        else:
                            print(f"\n⚠️  WARNING: May have returned code instead of name: '{diagnosis_value}'")
                
            else:
                error = data.get("error", "Unknown error")
                print(f"\n❌ Query Failed: {error}")
                print("\n" + "="*80)
                print("❌ TEST FAILED")
                print("="*80)
        
        else:
            print(f"\n❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            print("\n" + "="*80)
            print("❌ TEST FAILED")
            print("="*80)
    
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection Error: Could not connect to endpoint")
        print(f"   Make sure the server is running at {BASE_URL}")
        print("   Try: cd /root/hiva/services/ai/admin_chat && uvicorn main:app --reload")
        print("\n" + "="*80)
        print("❌ TEST FAILED - Server not running")
        print("="*80)
        return False
    
    except requests.exceptions.Timeout:
        print("\n❌ Timeout Error: Request took too long")
        print("\n" + "="*80)
        print("❌ TEST FAILED - Timeout")
        print("="*80)
        return False
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*80)
        print("❌ TEST FAILED")
        print("="*80)
        return False
    
    return True


if __name__ == "__main__":
    query = "show me the disease with highest number of patients"
    
    # Check for custom endpoint
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        ENDPOINT = f"{BASE_URL}/api/v1/admin/query"
    
    # Check for auth token
    auth_token = None
    if len(sys.argv) > 2:
        auth_token = sys.argv[2]
    
    test_endpoint(query, auth_token=auth_token)

