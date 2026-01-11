#!/usr/bin/env python3
"""
Auto-Discovery Script for AI Services
Scans active listening ports, probes HTTP responses, and identifies AI services.
"""

import json
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import httpx
import psutil


@dataclass
class DiscoveredService:
    """Represents a discovered AI service"""
    port: int
    service_name: str
    health_endpoint: str
    base_url: str
    process_name: str
    pid: Optional[int]
    is_healthy: bool
    response_time_ms: float
    discovery_method: str  # "env_var", "package_name", "app_title", "fallback"
    subdomain: str


class ServiceDiscovery:
    """Discovers running AI services on the host"""
    
    def __init__(self, base_domain: str = "hiva.chat", timeout: float = 2.0):
        self.base_domain = base_domain
        self.timeout = timeout
        self.discovered_services: List[DiscoveredService] = []
        
    def scan_listening_ports(self) -> List[Tuple[int, int]]:
        """Scan for listening TCP ports and return (port, pid) tuples"""
        ports = []
        try:
            # Use ss command for better reliability
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Parse ss output: LISTEN 0 4096 0.0.0.0:8000 0.0.0.0:* users:(("uvicorn",pid=1234,fd=5))
            for line in result.stdout.split('\n'):
                if 'LISTEN' in line and ':' in line:
                    # Extract port
                    port_match = re.search(r':(\d+)\s', line)
                    if port_match:
                        port = int(port_match.group(1))
                        # Extract PID
                        pid_match = re.search(r'pid=(\d+)', line)
                        pid = int(pid_match.group(1)) if pid_match else None
                        
                        # Only consider ports in typical service range (8000-8999, 8300-8399)
                        if 8000 <= port <= 8999 or port == 8300:
                            ports.append((port, pid))
        except Exception as e:
            print(f"⚠️  Error scanning ports: {e}", file=sys.stderr)
            
        return ports
    
    def probe_http_service(self, port: int) -> Optional[Dict]:
        """Probe a port for HTTP service and return service info"""
        base_url = f"http://localhost:{port}"
        
        # Try health endpoints in order
        health_endpoints = ["/health", "/status", "/"]
        
        for endpoint in health_endpoints:
            try:
                url = f"{base_url}{endpoint}"
                start_time = time.time()
                response = httpx.get(url, timeout=self.timeout, follow_redirects=True)
                response_time = (time.time() - start_time) * 1000
                
                # Check if it's a valid HTTP response
                if response.status_code in [200, 404]:  # 404 is OK, means service exists
                    # Try to get JSON response for service info
                    try:
                        data = response.json()
                        return {
                            "base_url": base_url,
                            "health_endpoint": endpoint,
                            "status_code": response.status_code,
                            "response_time_ms": response_time,
                            "is_healthy": response.status_code == 200,
                            "data": data
                        }
                    except:
                        # Not JSON, but still a valid HTTP service
                        return {
                            "base_url": base_url,
                            "health_endpoint": endpoint,
                            "status_code": response.status_code,
                            "response_time_ms": response_time,
                            "is_healthy": response.status_code == 200,
                            "data": None
                        }
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
                continue
            except Exception as e:
                print(f"⚠️  Error probing {url}: {e}", file=sys.stderr)
                continue
        
        return None
    
    def get_service_name(self, port: int, pid: Optional[int], http_data: Optional[Dict]) -> Tuple[str, str]:
        """
        Determine service name using priority order:
        1. Environment variable SERVICE_NAME
        2. FastAPI app.title from HTTP response
        3. Python package/directory name from process
        4. Fallback: ai-service-<port>
        
        Returns: (service_name, discovery_method)
        """
        # Method 1: Check environment variable
        if pid:
            try:
                proc = psutil.Process(pid)
                env = proc.environ()
                if 'SERVICE_NAME' in env:
                    return (env['SERVICE_NAME'], "env_var")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Method 2: Check FastAPI app.title from HTTP response
        if http_data and http_data.get('data'):
            data = http_data['data']
            if isinstance(data, dict):
                # Check for service name in various formats
                if 'service' in data and isinstance(data['service'], str):
                    return (data['service'], "app_title")
                if 'title' in data and isinstance(data['title'], str):
                    # FastAPI app.title might be like "Hiva Admin Chat API"
                    # Normalize it
                    title = data['title'].lower().replace(' ', '-').replace('_', '-')
                    return (title, "app_title")
        
        # Method 3: Try to infer from process command line and working directory
        if pid:
            try:
                proc = psutil.Process(pid)
                cmdline = ' '.join(proc.cmdline())
                cwd = proc.cwd()
                
                # Check for common patterns in command line
                if 'admin_chat' in cmdline.lower() or 'admin_chat' in cwd:
                    return ("hiva-admin-chat", "package_name")
                if 'claims_automation' in cmdline.lower() or 'claims_automation' in cwd:
                    return ("dcal-ai-engine", "package_name")
                if 'dcal' in cmdline.lower() or '/dcal' in cwd:
                    return ("dcal-ai-engine", "package_name")
                if 'app.main' in cmdline or 'app/main.py' in cmdline or '/app/main.py' in cwd:
                    # Check if it's in admin_chat or main app directory
                    if 'admin_chat' in cwd:
                        return ("hiva-admin-chat", "package_name")
                    return ("hiva-ai", "package_name")
                
                # Check working directory for service indicators
                if 'admin_chat' in cwd:
                    return ("hiva-admin-chat", "package_name")
                if 'claims_automation' in cwd:
                    return ("dcal-ai-engine", "package_name")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Method 4: Fallback
        return (f"ai-service-{port}", "fallback")
    
    def normalize_subdomain(self, service_name: str) -> str:
        """Convert service name to valid subdomain"""
        # Lowercase
        subdomain = service_name.lower()
        
        # Replace underscores and spaces with hyphens
        subdomain = re.sub(r'[_\s]+', '-', subdomain)
        
        # Remove invalid characters (keep only alphanumeric and hyphens)
        subdomain = re.sub(r'[^a-z0-9\-]', '', subdomain)
        
        # Remove leading/trailing hyphens
        subdomain = subdomain.strip('-')
        
        # Ensure it doesn't start with a number
        if subdomain and subdomain[0].isdigit():
            subdomain = f"svc-{subdomain}"
        
        # Ensure minimum length
        if len(subdomain) < 3:
            subdomain = f"svc-{subdomain}"
        
        return subdomain
    
    def discover_services(self) -> List[DiscoveredService]:
        """Main discovery method"""
        print("🔍 Scanning for AI services...")
        
        ports = self.scan_listening_ports()
        print(f"   Found {len(ports)} candidate ports")
        
        discovered = []
        subdomain_map = {}  # Track subdomains to prevent collisions
        
        for port, pid in ports:
            print(f"\n📡 Probing port {port}...")
            
            # Probe HTTP service
            http_info = self.probe_http_service(port)
            if not http_info:
                print(f"   ⚠️  Port {port} does not respond to HTTP")
                continue
            
            # Get service name
            service_name, discovery_method = self.get_service_name(port, pid, http_info)
            print(f"   ✅ Service: {service_name} (via {discovery_method})")
            
            # Get process name
            process_name = "unknown"
            if pid:
                try:
                    proc = psutil.Process(pid)
                    process_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Normalize subdomain
            subdomain = self.normalize_subdomain(service_name)
            
            # Check for collisions
            if subdomain in subdomain_map:
                print(f"   ❌ Subdomain collision: {subdomain} already used by port {subdomain_map[subdomain]}")
                # Append port to make unique
                subdomain = f"{subdomain}-{port}"
                print(f"   🔄 Using: {subdomain}")
            
            subdomain_map[subdomain] = port
            
            # Create discovered service
            service = DiscoveredService(
                port=port,
                service_name=service_name,
                health_endpoint=http_info['health_endpoint'],
                base_url=http_info['base_url'],
                process_name=process_name,
                pid=pid,
                is_healthy=http_info['is_healthy'],
                response_time_ms=http_info['response_time_ms'],
                discovery_method=discovery_method,
                subdomain=subdomain
            )
            
            discovered.append(service)
            print(f"   🌐 Subdomain: {subdomain}.{self.base_domain}")
        
        self.discovered_services = discovered
        return discovered
    
    def generate_report(self) -> Dict:
        """Generate discovery report"""
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_domain": self.base_domain,
            "services_discovered": len(self.discovered_services),
            "services": [asdict(s) for s in self.discovered_services]
        }
    
    def print_table(self):
        """Print discovery results as a table"""
        if not self.discovered_services:
            print("\n❌ No services discovered")
            return
        
        print("\n" + "="*100)
        print("DISCOVERY RESULTS")
        print("="*100)
        print(f"{'Service Name':<25} {'Port':<8} {'Subdomain':<30} {'Health':<10} {'Method':<15}")
        print("-"*100)
        
        for svc in self.discovered_services:
            health_status = "✅ Healthy" if svc.is_healthy else "⚠️  Unhealthy"
            print(f"{svc.service_name:<25} {svc.port:<8} {svc.subdomain:<30} {health_status:<10} {svc.discovery_method:<15}")
        
        print("="*100)
        print(f"\nTotal: {len(self.discovered_services)} service(s) discovered")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-discover AI services")
    parser.add_argument("--base-domain", default="hiva.chat", help="Base domain for subdomains")
    parser.add_argument("--timeout", type=float, default=2.0, help="HTTP timeout in seconds")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    discovery = ServiceDiscovery(base_domain=args.base_domain, timeout=args.timeout)
    services = discovery.discover_services()
    
    if not args.quiet:
        discovery.print_table()
    
    report = discovery.generate_report()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        if not args.quiet:
            print(f"\n✅ Report saved to {args.output}")
    
    # Exit with error if no services found
    if not services:
        sys.exit(1)
    
    # Exit with error if any service is unhealthy
    unhealthy = [s for s in services if not s.is_healthy]
    if unhealthy:
        if not args.quiet:
            print(f"\n⚠️  Warning: {len(unhealthy)} service(s) are unhealthy")
        sys.exit(2)


if __name__ == "__main__":
    main()
