"""
Stack management commands for ABI platform.
Manages Docker services, APIs, and frontend orchestration.
"""

import os
import subprocess
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Get project root from environment or current working directory
PROJECT_ROOT = Path(os.environ.get("ABI_PROJECT_ROOT", os.getcwd()))
if not (PROJECT_ROOT / "libs/naas-abi").exists():
    # Fallback: traverse up from this file
    PROJECT_ROOT = Path(__file__).resolve()
    for _ in range(10):  # Max 10 levels up
        if (PROJECT_ROOT / "libs/naas-abi").exists():
            break
        PROJECT_ROOT = PROJECT_ROOT.parent
    else:
        # Last resort: assume we're in the project root
        PROJECT_ROOT = Path.cwd()

NEXUS_DIR = PROJECT_ROOT / "libs/naas-abi/naas_abi/apps/nexus"


def _check_port(port: int) -> bool:
    """Check if a port is in use."""
    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0


def _kill_port(port: int) -> None:
    """Kill process on a port."""
    subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
        check=False
    ).stdout.strip()
    
    if _check_port(port):
        subprocess.run(
            f"lsof -ti:{port} | xargs kill -9",
            shell=True,
            capture_output=True,
            check=False
        )


def _check_docker() -> bool:
    """Check if Docker is running."""
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False
    )
    return result.returncode == 0


def _start_docker() -> None:
    """Start Docker Desktop."""
    if not _check_docker():
        console.print("🐳 Starting Docker Desktop...")
        subprocess.run(["open", "-a", "Docker"], check=False)
        
        for i in range(30):
            if _check_docker():
                console.print("   ✓ Docker ready")
                return
            time.sleep(1)
        
        console.print("   ⚠ Docker startup timeout", style="yellow")


def _start_docker_services() -> None:
    """Start Docker Compose services."""
    console.print("1️⃣  Starting infrastructure...")
    
    _start_docker()
    
    # Check if docker-compose.yml exists
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    if not compose_file.exists():
        console.print(f"   ⚠ docker-compose.yml not found at {compose_file}", style="yellow")
        return
    
    result = subprocess.run(
        ["docker", "compose", "up", "-d", "postgres", "fuseki"],
        cwd=str(PROJECT_ROOT),  # Convert Path to string
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode == 0:
        console.print("   ✓ PostgreSQL and Fuseki starting")
    else:
        console.print(f"   ⚠ Docker services: {result.stderr}", style="yellow")


def _start_abi_core() -> None:
    """Start ABI Core API on port 8001."""
    console.print("2️⃣  Starting ABI Core API (8001)...")
    
    if _check_port(8001):
        _kill_port(8001)
        time.sleep(1)
    
    log_file = "/tmp/abi-core-api.log"
    subprocess.Popen(
        ["uv", "run", "uvicorn", "naas_abi_core.apps.api.api:app", 
         "--host", "0.0.0.0", "--port", "8001"],
        cwd=str(PROJECT_ROOT),  # Convert Path to string
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    
    console.print("   ✓ Agent engine starting")


def _start_nexus_api() -> None:
    """Start Nexus API on port 9879."""
    console.print("4️⃣  Starting Nexus API (9879)...")
    
    if _check_port(9879):
        _kill_port(9879)
        time.sleep(1)
    
    log_file = "/tmp/nexus-api.log"
    subprocess.Popen(
        ["uv", "run", "uvicorn", "naas_abi.apps.nexus.apps.api.app.main:app",
         "--host", "0.0.0.0", "--port", "9879"],
        cwd=str(PROJECT_ROOT),  # Convert Path to string
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    
    console.print("   ✓ Platform API starting")


def _start_nexus_web() -> None:
    """Start Nexus Web on port 3000."""
    console.print("6️⃣  Starting Nexus Web (3000)...")
    
    if _check_port(3000):
        _kill_port(3000)
        time.sleep(1)
    
    web_dir = NEXUS_DIR / "apps/web"
    
    if not web_dir.exists():
        console.print(f"   ⚠ Web directory not found: {web_dir}", style="yellow")
        console.print(f"   Project root: {PROJECT_ROOT}", style="dim")
        return
    
    log_file = "/tmp/nexus-web.log"
    subprocess.Popen(
        ["pnpm", "dev"],
        cwd=str(web_dir),  # Convert Path to string
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "PORT": "3000"}
    )
    
    console.print("   ✓ Frontend starting")


def _wait_for_service(url: str, name: str, timeout: int = 30) -> bool:
    """Wait for a service to be healthy."""
    import requests
    
    console.print(f"   Waiting for {name}...")
    
    for i in range(timeout):
        try:
            response = requests.get(url, timeout=1)
            if response.status_code in (200, 404):  # 404 is ok, means server is up
                console.print(f"   ✓ {name} ready")
                return True
        except:
            pass
        time.sleep(1)
    
    console.print(f"   ⚠ {name} not available (non-fatal)", style="yellow")
    return False


@click.group()
def stack():
    """Manage ABI platform stack."""
    pass


@stack.command()
def start():
    """Start all ABI platform services."""
    console.print("🚀 Starting ABI Stack...\n", style="bold blue")
    
    # 1. Infrastructure
    _start_docker_services()
    time.sleep(3)
    
    # 2. ABI Core API
    _start_abi_core()
    
    # 3. Wait for Core (non-blocking)
    console.print("3️⃣  Waiting for agent engine...")
    if not _wait_for_service("http://localhost:8001/health", "ABI Core", timeout=10):
        console.print("   ⚠ Agents disabled (check logs)", style="yellow")
    
    # 4. Nexus API
    _start_nexus_api()
    
    # 5. Wait for API
    console.print("5️⃣  Waiting for platform API...")
    _wait_for_service("http://localhost:9879/health", "Nexus API")
    
    # 6. Nexus Web
    _start_nexus_web()
    
    # 7. Wait for Web
    console.print("7️⃣  Compiling frontend...")
    time.sleep(8)
    if _wait_for_service("http://localhost:3000", "Nexus Web", timeout=30):
        console.print("   ✓ Frontend ready")
    
    # Summary
    console.print("\n" + "━" * 60, style="blue")
    console.print("\n✅ ABI Platform is ready\n", style="bold green")
    console.print("🌐 Nexus:    http://localhost:3000", style="cyan")
    console.print("\n📊 Services:")
    console.print("   • Agents:   http://localhost:8001")
    console.print("   • API:      http://localhost:9879")
    console.print("   • Fuseki:   http://localhost:3030")
    console.print("   • Database: localhost:5432")
    console.print("\n💡 Quick:")
    console.print("   abi stack logs         BFO-structured logs")
    console.print("   abi chat               Agent chat")
    console.print("\n" + "━" * 60 + "\n", style="blue")
    
    # Open browser
    subprocess.run(["open", "http://localhost:3000"], check=False)


@stack.command()
def stop():
    """Stop ABI platform services (keeps Docker running)."""
    console.print("🛑 Stopping ABI Stack...", style="bold red")
    
    services_stopped = []
    
    # Stop ABI Core
    if _check_port(8001):
        _kill_port(8001)
        services_stopped.append("ABI Core")
    
    # Stop Nexus API
    if _check_port(9879):
        _kill_port(9879)
        services_stopped.append("Nexus API")
    
    # Stop Nexus Web
    if _check_port(3000):
        _kill_port(3000)
        services_stopped.append("Web")
    
    if services_stopped:
        for service in services_stopped:
            console.print(f"   ✓ {service} stopped")
    else:
        console.print("   • No services were running")
    
    console.print("✅ Stack stopped\n", style="green")


@stack.command()
def status():
    """Show comprehensive status of all services."""
    import requests
    import json
    
    console.print("📊 ABI Platform Status\n", style="bold blue")
    console.print("━" * 60)
    
    # Check PostgreSQL
    pg_status = "✅" if _check_port(5432) else "❌"
    console.print(f"{pg_status} PostgreSQL    localhost:5432")
    
    # Check Fuseki
    fuseki_status = "❌"
    triples_count = 0
    try:
        response = requests.get("http://localhost:3030/ds/query", 
                               params={"query": "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"},
                               auth=("admin", "abi"),
                               timeout=2)
        if response.status_code == 200:
            result = response.json()
            triples_count = int(result['results']['bindings'][0]['count']['value'])
            fuseki_status = "✅"
    except:
        pass
    
    console.print(f"{fuseki_status} Fuseki        http://localhost:3030    [{triples_count:,} triples]")
    
    # Check ABI Core
    core_status = "❌"
    if _check_port(8001):
        try:
            response = requests.get("http://localhost:8001/health", timeout=1)
            core_status = "✅" if response.status_code == 200 else "⚠️"
        except:
            core_status = "⚠️"
    console.print(f"{core_status} ABI Core API  http://localhost:8001")
    
    # Check Nexus API
    api_status = "❌"
    if _check_port(9879):
        try:
            response = requests.get("http://localhost:9879/health", timeout=1)
            api_status = "✅" if response.status_code == 200 else "⚠️"
        except:
            api_status = "⚠️"
    console.print(f"{api_status} Nexus API     http://localhost:9879")
    
    # Check Nexus Web
    web_status = "✅" if _check_port(3000) else "❌"
    console.print(f"{web_status} Nexus Web     http://localhost:3000")
    
    console.print("━" * 60)
    
    # Overall status
    all_up = all([
        _check_port(5432),
        fuseki_status == "✅",
        _check_port(9879),
        _check_port(3000)
    ])
    
    if all_up:
        console.print("\n✅ All services running\n", style="green")
    else:
        console.print("\n🟡 Partial (some services down)\n", style="yellow")
    
    console.print("💡 Quick:")
    console.print("   abi stack logs         Stream live logs")
    console.print("   abi chat               Start agent chat")
    console.print("   abi stack start        Start all services\n")


@stack.command()
@click.argument("service", required=False, default="all")
@click.option("--raw", is_flag=True, help="Stream raw logs without BFO parsing")
def logs(service: str, raw: bool):
    """Stream BFO-structured logs inline (Ctrl+C to stop).
    
    SERVICE can be: core, api, web, or all (default)
    """
    import sys
    
    bfo_parser = PROJECT_ROOT / "scripts/bfo_logs.py"
    log_files = {
        "core": "/tmp/abi-core-api.log",
        "api": "/tmp/nexus-api.log",
        "web": "/tmp/nexus-web.log",
    }
    
    if service == "all":
        console.print("📜 ABI Platform Logs (BFO-structured) - Press Ctrl+C to stop\n", style="bold blue")
        
        if not raw:
            console.print("🟣 T:TIME  🟠 S:SPACE  🟢 P:PROCESS  🔵 M:MATERIAL  🔷 D:DATA  🩷 Q:QUALITIES  🟡 R:DISPOSITION\n")
        
        # Multi-tail with BFO parsing or labels
        processes = []
        try:
            for svc_name, log_file in log_files.items():
                if raw:
                    # Simple tail with service labels
                    proc = subprocess.Popen(
                        f"tail -f {log_file} 2>/dev/null | sed 's/^/[{svc_name.upper()}] /'",
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True
                    )
                else:
                    # BFO parser
                    proc = subprocess.Popen(
                        ["tail", "-f", log_file],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True
                    )
                    bfo_proc = subprocess.Popen(
                        ["python3", str(bfo_parser), svc_name],
                        stdin=proc.stdout,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True
                    )
                    processes.append(proc)
                    proc = bfo_proc
                
                processes.append(proc)
                
                # Stream output
                def stream_output(p):
                    try:
                        for line in p.stdout:
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except:
                        pass
                
                import threading
                thread = threading.Thread(target=stream_output, args=(proc,), daemon=True)
                thread.start()
            
            # Wait forever (until Ctrl+C)
            import signal
            signal.pause()
        
        except KeyboardInterrupt:
            console.print("\n\n✅ Stopped log streaming", style="green")
        finally:
            for proc in processes:
                proc.terminate()
    
    else:
        # Single service
        service_map = {
            "core": "core",
            "agent": "core",
            "agents": "core",
            "api": "api",
            "nexus": "api",
            "web": "web",
            "frontend": "web",
        }
        
        svc = service_map.get(service)
        if not svc:
            console.print(f"❌ Unknown service: {service}", style="red")
            console.print("Use: core, api, web, or all")
            return
        
        log_file = log_files[svc]
        console.print(f"📜 Streaming {svc.upper()} logs - Press Ctrl+C to stop\n", style="bold blue")
        
        try:
            if raw:
                # Simple tail
                subprocess.run(
                    ["tail", "-f", log_file],
                    check=False
                )
            else:
                # BFO parser
                tail_proc = subprocess.Popen(
                    ["tail", "-f", log_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True
                )
                bfo_proc = subprocess.Popen(
                    ["python3", str(bfo_parser), svc],
                    stdin=tail_proc.stdout,
                    stdout=sys.stdout,
                    stderr=subprocess.DEVNULL
                )
                
                bfo_proc.wait()
        
        except KeyboardInterrupt:
            console.print("\n\n✅ Stopped log streaming", style="green")
