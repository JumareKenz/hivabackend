#!/usr/bin/env python3
"""
Service Validation Script
Validates discovered services for stability, isolation, and health.
"""

import json
import sys
import time
import asyncio
from pathlib import Path
from typing import List, Dict
import httpx


class ServiceValidator:
    """Validates services before NGINX configuration"""
    
    def __init__(self, timeout: float = 5.0, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        
    def validate_service(self, service: Dict) -> Dict:
        """Validate a single service"""
        port = service['port']
        service_name = service['service_name']
        health_endpoint = service['health_endpoint']
        base_url = service['base_url']
        
        print(f"\n🔍 Validating {service_name} (port {port})...")
        
        results = {
            "service_name": service_name,
            "port": port,
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks": {}
        }
        
        # Check 1: HTTP 200 response
        print("   [1/4] Checking HTTP 200 response...")
        try:
            url = f"{base_url}{health_endpoint}"
            response = httpx.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                results["checks"]["http_200"] = True
                print("      ✅ HTTP 200 OK")
            else:
                results["checks"]["http_200"] = False
                results["warnings"].append(f"Health endpoint returned {response.status_code}")
                print(f"      ⚠️  HTTP {response.status_code}")
        except Exception as e:
            results["checks"]["http_200"] = False
            results["errors"].append(f"Health check failed: {e}")
            results["valid"] = False
            print(f"      ❌ Health check failed: {e}")
        
        # Check 2: Response stability (multiple requests)
        print("   [2/4] Checking response stability...")
        try:
            url = f"{base_url}{health_endpoint}"
            responses = []
            for i in range(self.retries):
                response = httpx.get(url, timeout=self.timeout)
                responses.append(response.status_code)
                time.sleep(0.5)  # Small delay between requests
            
            if len(set(responses)) == 1 and responses[0] == 200:
                results["checks"]["stability"] = True
                print(f"      ✅ Stable ({self.retries} consistent responses)")
            else:
                results["checks"]["stability"] = False
                results["warnings"].append(f"Inconsistent responses: {responses}")
                print(f"      ⚠️  Inconsistent: {responses}")
        except Exception as e:
            results["checks"]["stability"] = False
            results["errors"].append(f"Stability check failed: {e}")
            results["valid"] = False
            print(f"      ❌ Stability check failed: {e}")
        
        # Check 3: Isolation (no shared state assumptions)
        print("   [3/4] Checking service isolation...")
        try:
            # Make concurrent requests to check for shared state issues
            url = f"{base_url}{health_endpoint}"
            
            async def concurrent_check():
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    tasks = [client.get(url) for _ in range(3)]
                    responses = await asyncio.gather(*tasks, return_exceptions=True)
                    return responses
            
            import asyncio
            responses = asyncio.run(concurrent_check())
            
            # Check if all responses are successful
            successful = sum(1 for r in responses if isinstance(r, httpx.Response) and r.status_code == 200)
            
            if successful == len(responses):
                results["checks"]["isolation"] = True
                print(f"      ✅ Isolated ({successful}/{len(responses)} successful)")
            else:
                results["checks"]["isolation"] = False
                results["warnings"].append(f"Concurrent requests: {successful}/{len(responses)} successful")
                print(f"      ⚠️  Isolation concerns: {successful}/{len(responses)} successful")
        except Exception as e:
            results["checks"]["isolation"] = False
            results["warnings"].append(f"Isolation check incomplete: {e}")
            print(f"      ⚠️  Isolation check incomplete: {e}")
        
        # Check 4: Response time
        print("   [4/4] Checking response time...")
        try:
            url = f"{base_url}{health_endpoint}"
            start = time.time()
            response = httpx.get(url, timeout=self.timeout)
            elapsed = (time.time() - start) * 1000
            
            if elapsed < 1000:  # Less than 1 second
                results["checks"]["response_time"] = True
                results["checks"]["response_time_ms"] = elapsed
                print(f"      ✅ Fast response ({elapsed:.0f}ms)")
            else:
                results["checks"]["response_time"] = False
                results["checks"]["response_time_ms"] = elapsed
                results["warnings"].append(f"Slow response: {elapsed:.0f}ms")
                print(f"      ⚠️  Slow response ({elapsed:.0f}ms)")
        except Exception as e:
            results["checks"]["response_time"] = False
            results["errors"].append(f"Response time check failed: {e}")
            print(f"      ❌ Response time check failed: {e}")
        
        # Final validation status
        if results["errors"]:
            results["valid"] = False
            print(f"   ❌ Validation FAILED: {len(results['errors'])} error(s)")
        elif results["warnings"]:
            print(f"   ⚠️  Validation PASSED with {len(results['warnings'])} warning(s)")
        else:
            print(f"   ✅ Validation PASSED")
        
        return results
    
    def validate_all(self, services: List[Dict]) -> Dict:
        """Validate all services"""
        print("="*80)
        print("SERVICE VALIDATION")
        print("="*80)
        print(f"Validating {len(services)} service(s)...\n")
        
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_services": len(services),
            "valid_services": 0,
            "invalid_services": 0,
            "services": []
        }
        
        for service in services:
            validation = self.validate_service(service)
            results["services"].append(validation)
            
            if validation["valid"]:
                results["valid_services"] += 1
            else:
                results["invalid_services"] += 1
        
        # Print summary
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"Total services: {results['total_services']}")
        print(f"✅ Valid: {results['valid_services']}")
        print(f"❌ Invalid: {results['invalid_services']}")
        
        if results["invalid_services"] > 0:
            print("\n⚠️  Invalid services:")
            for svc in results["services"]:
                if not svc["valid"]:
                    print(f"   - {svc['service_name']} (port {svc['port']}): {', '.join(svc['errors'])}")
        
        return results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate discovered services")
    parser.add_argument("--discovery-report", required=True, help="Path to discovery report JSON")
    parser.add_argument("--output", help="Output validation report JSON path")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Number of retries for stability check")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit with error if validation fails")
    
    args = parser.parse_args()
    
    # Load discovery report
    report_path = Path(args.discovery_report)
    if not report_path.exists():
        print(f"❌ Discovery report not found: {report_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(report_path, 'r') as f:
        discovery_report = json.load(f)
    
    services = discovery_report.get('services', [])
    
    if not services:
        print("❌ No services found in discovery report", file=sys.stderr)
        sys.exit(1)
    
    # Validate services
    validator = ServiceValidator(timeout=args.timeout, retries=args.retries)
    validation_results = validator.validate_all(services)
    
    # Save report
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(validation_results, f, indent=2)
        print(f"\n✅ Validation report saved to {output_path}")
    
    # Exit with error if validation failed
    if args.fail_on_error and validation_results["invalid_services"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
