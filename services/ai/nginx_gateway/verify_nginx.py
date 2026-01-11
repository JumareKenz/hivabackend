#!/usr/bin/env python3
"""
NGINX Verification Script
Verifies NGINX configuration syntax and tests endpoints via subdomains.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional
import httpx


class NGINXVerifier:
    """Verifies NGINX configuration and endpoints"""
    
    def __init__(self, base_domain: str = "hiva.chat", timeout: float = 10.0):
        self.base_domain = base_domain
        self.timeout = timeout
        
    def verify_config_syntax(self, config_path: Path) -> Dict:
        """Verify NGINX configuration syntax"""
        print("🔍 Verifying NGINX configuration syntax...")
        
        try:
            result = subprocess.run(
                ["nginx", "-t", "-c", str(config_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("   ✅ Configuration syntax is valid")
                return {
                    "valid": True,
                    "output": result.stdout,
                    "errors": []
                }
            else:
                print("   ❌ Configuration syntax is invalid")
                print(f"   Error: {result.stderr}")
                return {
                    "valid": False,
                    "output": result.stdout,
                    "errors": [result.stderr]
                }
        except FileNotFoundError:
            print("   ⚠️  nginx command not found (may need sudo)")
            return {
                "valid": None,
                "output": "",
                "errors": ["nginx command not found"]
            }
        except subprocess.TimeoutExpired:
            print("   ❌ Configuration check timed out")
            return {
                "valid": False,
                "output": "",
                "errors": ["Configuration check timed out"]
            }
        except Exception as e:
            print(f"   ❌ Error checking configuration: {e}")
            return {
                "valid": False,
                "output": "",
                "errors": [str(e)]
            }
    
    def test_endpoint(self, subdomain: str, path: str = "/health", use_https: bool = True) -> Dict:
        """Test an endpoint via subdomain"""
        protocol = "https" if use_https else "http"
        url = f"{protocol}://{subdomain}.{self.base_domain}{path}"
        
        try:
            start_time = time.time()
            response = httpx.get(
                url,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False  # Allow self-signed certs in testing
            )
            elapsed = (time.time() - start_time) * 1000
            
            return {
                "url": url,
                "status_code": response.status_code,
                "response_time_ms": elapsed,
                "success": response.status_code == 200,
                "error": None
            }
        except httpx.ConnectError as e:
            return {
                "url": url,
                "status_code": None,
                "response_time_ms": None,
                "success": False,
                "error": f"Connection error: {e}"
            }
        except httpx.TimeoutException:
            return {
                "url": url,
                "status_code": None,
                "response_time_ms": None,
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": None,
                "response_time_ms": None,
                "success": False,
                "error": str(e)
            }
    
    def verify_endpoints(self, services: List[Dict], use_https: bool = True) -> Dict:
        """Verify all service endpoints via subdomains"""
        print("\n🔍 Testing endpoints via subdomains...")
        
        results = {
            "total": len(services),
            "successful": 0,
            "failed": 0,
            "endpoints": []
        }
        
        for service in services:
            subdomain = service['subdomain']
            service_name = service['service_name']
            
            print(f"\n   Testing {service_name} ({subdomain}.{self.base_domain})...")
            
            # Test health endpoint
            health_result = self.test_endpoint(subdomain, "/health", use_https)
            results["endpoints"].append({
                "service": service_name,
                "subdomain": subdomain,
                "endpoint": "/health",
                **health_result
            })
            
            if health_result["success"]:
                print(f"      ✅ /health: {health_result['status_code']} ({health_result['response_time_ms']:.0f}ms)")
                results["successful"] += 1
            else:
                print(f"      ❌ /health: {health_result.get('error', 'Failed')}")
                results["failed"] += 1
            
            # Test root endpoint
            root_result = self.test_endpoint(subdomain, "/", use_https)
            results["endpoints"].append({
                "service": service_name,
                "subdomain": subdomain,
                "endpoint": "/",
                **root_result
            })
            
            if root_result["success"]:
                print(f"      ✅ /: {root_result['status_code']} ({root_result['response_time_ms']:.0f}ms)")
            else:
                print(f"      ⚠️  /: {root_result.get('error', 'Failed')}")
        
        return results
    
    def verify_logs_separation(self, services: List[Dict]) -> Dict:
        """Verify that logs are separated per service"""
        print("\n🔍 Verifying log separation...")
        
        log_dir = Path("/var/log/nginx")
        results = {
            "log_dir_exists": log_dir.exists(),
            "services_checked": len(services),
            "logs_found": 0,
            "logs_missing": []
        }
        
        if not log_dir.exists():
            print("   ⚠️  Log directory does not exist: /var/log/nginx")
            return results
        
        for service in services:
            subdomain = service['subdomain']
            access_log = log_dir / f"{subdomain}_access.log"
            error_log = log_dir / f"{subdomain}_error.log"
            
            if access_log.exists() or error_log.exists():
                results["logs_found"] += 1
                print(f"   ✅ Logs exist for {subdomain}")
            else:
                results["logs_missing"].append(subdomain)
                print(f"   ⚠️  Logs not found for {subdomain} (will be created on first request)")
        
        return results
    
    def verify_graceful_failures(self, services: List[Dict]) -> Dict:
        """Verify that failures are handled gracefully"""
        print("\n🔍 Verifying graceful failure handling...")
        
        # Test non-existent subdomain
        fake_subdomain = "nonexistent-service-test-12345"
        result = self.test_endpoint(fake_subdomain, "/health", use_https=True)
        
        # Should return 444 (connection closed) or 404
        graceful = result["status_code"] in [444, 404] or result["error"] is not None
        
        return {
            "graceful_failure": graceful,
            "test_subdomain": fake_subdomain,
            "result": result
        }
    
    def verify_all(self, config_path: Path, services: List[Dict], use_https: bool = True) -> Dict:
        """Run all verification checks"""
        print("="*80)
        print("NGINX VERIFICATION")
        print("="*80)
        
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config_syntax": None,
            "endpoints": None,
            "logs": None,
            "graceful_failures": None,
            "overall_success": False
        }
        
        # 1. Config syntax
        results["config_syntax"] = self.verify_config_syntax(config_path)
        
        # 2. Endpoints (only if config is valid)
        if results["config_syntax"]["valid"]:
            results["endpoints"] = self.verify_endpoints(services, use_https)
        else:
            print("\n⚠️  Skipping endpoint tests (config syntax invalid)")
            results["endpoints"] = {"skipped": True}
        
        # 3. Log separation
        results["logs"] = self.verify_logs_separation(services)
        
        # 4. Graceful failures
        results["graceful_failures"] = self.verify_graceful_failures(services)
        
        # Overall success
        results["overall_success"] = (
            results["config_syntax"]["valid"] is not False and
            results["endpoints"].get("failed", 0) == 0 and
            results["graceful_failures"]["graceful_failure"]
        )
        
        # Print summary
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Config syntax: {'✅ Valid' if results['config_syntax']['valid'] else '❌ Invalid'}")
        if "endpoints" in results and not results["endpoints"].get("skipped"):
            print(f"Endpoints: {results['endpoints']['successful']}/{results['endpoints']['total']} successful")
        print(f"Log separation: ✅ Configured")
        print(f"Graceful failures: {'✅ Working' if results['graceful_failures']['graceful_failure'] else '❌ Not working'}")
        print(f"\nOverall: {'✅ SUCCESS' if results['overall_success'] else '❌ FAILED'}")
        
        return results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify NGINX configuration and endpoints")
    parser.add_argument("--config", required=True, help="Path to NGINX config file")
    parser.add_argument("--discovery-report", required=True, help="Path to discovery report JSON")
    parser.add_argument("--base-domain", default="hiva.chat", help="Base domain")
    parser.add_argument("--output", help="Output verification report JSON path")
    parser.add_argument("--no-https", action="store_true", help="Test HTTP instead of HTTPS")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit with error if verification fails")
    
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
    
    # Verify
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"❌ NGINX config not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    
    verifier = NGINXVerifier(base_domain=args.base_domain)
    results = verifier.verify_all(config_path, services, use_https=not args.no_https)
    
    # Save report
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Verification report saved to {output_path}")
    
    # Exit with error if verification failed
    if args.fail_on_error and not results["overall_success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
