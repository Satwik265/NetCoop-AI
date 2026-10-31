"""Process manager to launch, health-check, and cleanly shut down specialist agent microservices."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import httpx

PID_FILE = Path(__file__).parent.parent / ".agents.pid"

AGENT_ROLES = [
    ("telemetry_agent", 8001),
    ("topology_agent", 8002),
    ("config_agent", 8003),
    ("log_agent", 8004),
    ("synthesizer_agent", 8005),
    ("classifier_agent", 8007),
]

GATEWAY_SERVICE = ("gateway", 8006)


def start_agent_process(role: str, port: int, project_root: Path) -> subprocess.Popen:
    """Spawn an individual agent microservice as a child process."""
    cmd = [
        sys.executable,
        "-m",
        "agents.server",
        "--role",
        role,
        "--port",
        str(port),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    log_path = project_root / f".agent_{role}.log"
    log_f = open(log_path, "w", encoding="utf-8")

    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=log_f,
        stderr=log_f,
    )
    return process


def start_gateway_process(port: int, project_root: Path) -> subprocess.Popen:
    """Spawn the gateway microservice as a child process."""
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "gateway.api:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    log_path = project_root / ".agent_gateway.log"
    log_f = open(log_path, "w", encoding="utf-8")

    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=log_f,
        stderr=log_f,
    )
    return process


def wait_for_health(host: str, port: int, endpoint: str = "/health", timeout: float = 12.0) -> bool:
    """Poll microservice health endpoint until responsive or timed out."""
    url = f"http://{host}:{port}{endpoint}"
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def save_pids(pids: Dict[str, int]) -> None:
    """Save active process IDs to disk for clean termination."""
    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f, indent=2)


def load_pids() -> Dict[str, int]:
    """Load previously saved process IDs."""
    if not PID_FILE.exists():
        return {}
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def terminate_pid(pid: int) -> None:
    """Terminate process by PID across Windows and POSIX platforms."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def stop_all_agents() -> None:
    """Stop all recorded agent and gateway processes."""
    pids = load_pids()
    if not pids:
        print("No active agent processes recorded in .agents.pid", flush=True)
        return

    print("Stopping all running NetCoop specialist agents and gateway...", flush=True)
    for name, pid in pids.items():
        print(f"  Terminating {name} (PID: {pid})...", flush=True)
        terminate_pid(pid)

    if PID_FILE.exists():
        PID_FILE.unlink()
    print("All processes stopped cleanly.", flush=True)


def check_status() -> None:
    """Verify and print health status of all agent microservices."""
    pids = load_pids()
    all_services = AGENT_ROLES + [GATEWAY_SERVICE]

    print("NetCoop AI Agent Process Health Status:", flush=True)
    for role, port in all_services:
        is_healthy = wait_for_health("127.0.0.1", port, timeout=1.0)
        status_str = "HEALTHY" if is_healthy else "STOPPED / UNRESPONSIVE"
        pid = pids.get(role, "unknown")
        print(f"  {role:<22} port {port:<5} PID {pid:<8} [{status_str}]", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="NetCoop AI Specialist Agent Manager")
    parser.add_argument("--stop", "--down", dest="stop", action="store_true", help="Stop all running agents")
    parser.add_argument("--daemon", action="store_true", help="Start in background and return immediately")
    parser.add_argument("--status", action="store_true", help="Check status of running agents")
    args = parser.parse_args()

    if args.stop:
        stop_all_agents()
        return

    if args.status:
        check_status()
        return

    # First clean up any existing processes
    stop_all_agents()
    time.sleep(1.0)

    # Start processes
    project_root = Path(__file__).parent.parent.resolve()
    print("Launching NetCoop AI specialist agents and gateway...", flush=True)

    pids: Dict[str, int] = {}
    proc_handles: List[subprocess.Popen] = []

    # 1. Start Gateway
    gw_role, gw_port = GATEWAY_SERVICE
    gw_proc = start_gateway_process(gw_port, project_root)
    pids[gw_role] = gw_proc.pid
    proc_handles.append(gw_proc)

    # 2. Start Agents
    for role, port in AGENT_ROLES:
        proc = start_agent_process(role, port, project_root)
        pids[role] = proc.pid
        proc_handles.append(proc)

    save_pids(pids)

    # Give all processes a moment to bind sockets
    time.sleep(2.0)

    # 3. Wait for all health checks
    all_healthy = True
    for role, port in AGENT_ROLES + [GATEWAY_SERVICE]:
        healthy = wait_for_health("127.0.0.1", port, timeout=12.0)
        if healthy:
            print(f"  {role:<22} (port {port}): healthy", flush=True)
        else:
            print(f"  {role:<22} (port {port}): FAILED TO RESPOND", flush=True)
            all_healthy = False

    if not all_healthy:
        print("Warning: Some agents failed to respond within timeout.", flush=True)
        if not args.daemon:
            stop_all_agents()
            sys.exit(1)
    else:
        print("All specialist agent microservices and gateway are operational.", flush=True)

    if args.daemon:
        print("Agent processes running in background. Use --stop or 'make down' to terminate.", flush=True)
        return

    # Foreground mode: listen for SIGINT
    print("Press Ctrl+C to shut down all agents.", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nInterrupted by operator. Shutting down...", flush=True)
        stop_all_agents()


if __name__ == "__main__":
    main()
