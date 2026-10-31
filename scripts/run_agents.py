"""Process manager to launch, health-check, and cleanly shut down specialist agent microservices."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

PID_FILE = Path(__file__).parent.parent / ".agents.pid"
_OPEN_LOG_HANDLES: List[Any] = []

AGENT_ROLES = [
    ("telemetry_agent", 8001),
    ("topology_agent", 8002),
    ("config_agent", 8003),
    ("log_agent", 8004),
    ("synthesizer_agent", 8005),
    ("classifier_agent", 8007),
    ("wifi_services_agent", 8008),
]

GATEWAY_SERVICE = ("gateway", 8006)
ALL_PORTS = [8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008]


def get_python_executable(project_root: Path) -> str:
    """Find virtualenv Python interpreter or fall back to sys.executable."""
    venv_py = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    posix_py = project_root / ".venv" / "bin" / "python"
    if posix_py.exists():
        return str(posix_py)
    return sys.executable


def start_agent_process(role: str, port: int, project_root: Path) -> subprocess.Popen:
    """Spawn an individual agent microservice as a child process."""
    py_exec = get_python_executable(project_root)
    cmd = [
        py_exec,
        "-m",
        "agents.server",
        "--role",
        role,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    log_path = project_root / f".agent_{role}.log"
    log_f = open(log_path, "a", encoding="utf-8")
    _OPEN_LOG_HANDLES.append(log_f)

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=log_f,
        stderr=log_f,
        creationflags=creationflags,
    )
    return process


def start_gateway_process(port: int, project_root: Path) -> subprocess.Popen:
    """Spawn the gateway microservice as a child process."""
    py_exec = get_python_executable(project_root)
    cmd = [
        py_exec,
        "-m",
        "gateway.api",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    log_path = project_root / ".agent_gateway.log"
    log_f = open(log_path, "a", encoding="utf-8")
    _OPEN_LOG_HANDLES.append(log_f)

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=log_f,
        stderr=log_f,
        creationflags=creationflags,
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


def cleanup_orphaned_ports(ports: List[int]) -> None:
    """Clean up any orphan processes still bound to agent ports using fast netstat check."""
    if sys.platform == "win32":
        try:
            res = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, check=False)
            port_suffixes = {f":{p}" for p in ports}
            candidate_pids = set()
            for line in res.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and (parts[0].startswith("TCP") or parts[0].startswith("UDP")):
                    local_addr = parts[1]
                    for ps in port_suffixes:
                        if local_addr.endswith(ps):
                            pid_str = parts[-1]
                            if pid_str.isdigit():
                                candidate_pids.add(int(pid_str))
            for c_pid in candidate_pids:
                if c_pid != os.getpid() and c_pid > 0:
                    terminate_pid(c_pid)
        except Exception:
            pass


def stop_all_agents() -> None:
    """Stop all recorded agent and gateway processes and release file handles."""
    pids = load_pids()
    if pids:
        print("Stopping all running NetCoop specialist agents and gateway...", flush=True)
        for name, pid in pids.items():
            print(f"  Terminating {name} (PID: {pid})...", flush=True)
            terminate_pid(pid)
    else:
        print("No active agent processes recorded in .agents.pid", flush=True)

    # Clean up any unrecorded orphan processes holding agent ports
    cleanup_orphaned_ports(ALL_PORTS)

    # Flush and close open log handles
    for handle in _OPEN_LOG_HANDLES:
        try:
            handle.flush()
            handle.close()
        except Exception:
            pass
    _OPEN_LOG_HANDLES.clear()

    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception:
            pass
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
    time.sleep(4.0)

    # 3. Wait for all health checks concurrently
    all_services = AGENT_ROLES + [GATEWAY_SERVICE]
    pending = dict(all_services)
    health_results = {role: False for role, _ in all_services}
    start_wait = time.time()
    timeout = 30.0

    while pending and (time.time() - start_wait < timeout):
        for role in list(pending.keys()):
            port = pending[role]
            url = f"http://127.0.0.1:{port}/health"
            try:
                with httpx.Client(timeout=0.5) as client:
                    res = client.get(url)
                    if res.status_code == 200:
                        health_results[role] = True
                        del pending[role]
            except Exception:
                pass
        if pending:
            time.sleep(0.5)

    all_healthy = all(health_results.values())
    for role, port in all_services:
        if health_results[role]:
            print(f"  {role:<22} (port {port}): healthy", flush=True)
        else:
            print(f"  {role:<22} (port {port}): FAILED TO RESPOND", flush=True)

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
