"""
Simple script to trigger database inspection via API
"""
import requests
import sys

# API endpoint (adjust if needed)
API_URL = "http://localhost:8000/api/v1/admin/inspect-database"

# Admin token (set this or pass as argument)
ADMIN_TOKEN = sys.argv[1] if len(sys.argv) > 1 else None

if not ADMIN_TOKEN:
    print("Usage: python3 trigger_inspection.py <admin_token>")
    print("Or set ADMIN_TOKEN environment variable")
    sys.exit(1)

print("Triggering database inspection...")

response = requests.post(
    API_URL,
    headers={
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    },
    json={"force_refresh": True}
)

if response.status_code == 200:
    result = response.json()
    print("✅ Inspection complete!")
    print(f"Tables analyzed: {result.get('tables_analyzed', 0)}")
    print(f"Query patterns: {result.get('query_patterns', 0)}")
    print(f"Documentation: {result.get('documentation_file', 'N/A')}")
    print(f"Schema file: {result.get('schema_file', 'N/A')}")
else:
    print(f"❌ Inspection failed: {response.status_code}")
    print(response.text)

