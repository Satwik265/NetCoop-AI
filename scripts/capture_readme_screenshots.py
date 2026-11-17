#!/usr/bin/env python3
"""capture_readme_screenshots.py: Capture genuine, production-grade screenshots for README.md.

Launches the local backend microservices, orchestrator API, and Vite dev/preview server,
drives the application via Playwright, and captures high-resolution screenshots:
1. docs/assets/readme/dashboard.png
2. docs/assets/readme/network-topology.png
3. docs/assets/readme/agent-orchestration.png
4. docs/assets/readme/diagnostic-report.png
5. docs/assets/readme/evidence-provenance.png
6. docs/assets/readme/safe-abstention.png
7. docs/assets/readme/remediation-audit.png
"""

import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, Optional

import httpx
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
README_ASSETS_DIR = WORKSPACE_ROOT / "docs" / "assets" / "readme"
README_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

VENV_PYTHON = str(WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe")
DEV_PASSWORD = os.getenv("NETCOOP_DEV_PASSWORD", "NetCoopDev!2026")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "a1b2c3d4e5f67890123456789abcdef0")


def kill_proc(proc: Optional[subprocess.Popen]) -> None:
    """Terminate process tree cleanly on Windows."""
    if proc is None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=3.0)
    except Exception:
        pass


def wait_for_url(url: str, timeout: float = 25.0) -> bool:
    """Poll URL until it responds with HTTP 200."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with httpx.Client(timeout=1.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def start_orchestrator(env: Dict[str, str]) -> subprocess.Popen:
    """Launch Orchestrator API on port 8000."""
    cmd = [
        VENV_PYTHON,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--log-level",
        "warning",
    ]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return proc


def start_frontend() -> subprocess.Popen:
    """Launch Frontend Vite dev server on port 5173."""
    cmd = ["cmd.exe", "/c", "npx", "vite", "--port", "5173", "--host", "127.0.0.1"]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE_ROOT / "dashboard"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    return proc


def capture_all_screenshots():
    print("[*] Starting NetCoop backend microservices and Vite dev server...")
    env = os.environ.copy()
    env["INTERNAL_SERVICE_TOKEN"] = INTERNAL_SERVICE_TOKEN
    env["NETCOOP_DEV_PASSWORD"] = DEV_PASSWORD
    env["NETCOOP_ENV"] = "development"
    env["NETCOOP_DEMO_MODE"] = "true"
    env["PYTHONPATH"] = str(WORKSPACE_ROOT)
    env.pop("AGENTS_MODE", None)

    # 1. Start agents daemon
    subprocess.run(
        [VENV_PYTHON, "scripts/run_agents.py", "--daemon"],
        cwd=str(WORKSPACE_ROOT),
        env=env,
        check=True,
    )

    orch_proc = start_orchestrator(env)
    frontend_proc = start_frontend()

    try:
        print("[*] Waiting for backend (http://127.0.0.1:8000/api/health)...")
        if not wait_for_url("http://127.0.0.1:8000/api/health", timeout=30.0):
            raise RuntimeError("Orchestrator failed to become healthy on port 8000")
        print("    Backend is online!")

        print("[*] Waiting for frontend (http://127.0.0.1:5173)...")
        if not wait_for_url("http://127.0.0.1:5173", timeout=30.0):
            raise RuntimeError("Frontend Vite server failed to become reachable on port 5173")
        print("    Frontend is online!")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1.5,
                color_scheme="dark",
            )
            page = context.new_page()

            # -------------------------------------------------------------
            # STEP 1: Navigate & Login
            # -------------------------------------------------------------
            print("[*] Navigating to http://127.0.0.1:5173...")
            page.goto("http://127.0.0.1:5173", wait_until="networkidle")
            page.evaluate("sessionStorage.clear()")
            page.reload(wait_until="networkidle")
            time.sleep(1.0)

            modal_header = page.locator("#login-modal-title").first
            if not modal_header.is_visible():
                login_btn = page.locator("button:has-text('Login')").first
                if login_btn.is_visible():
                    login_btn.click()
                    time.sleep(0.5)

            modal_header.wait_for(state="visible", timeout=10000)
            print("[*] Logging in as engineer...")
            page.locator("input#login-username").fill("engineer")
            page.locator("input#login-password").fill(DEV_PASSWORD)
            page.keyboard.press("Enter")
            time.sleep(1.5)

            # -------------------------------------------------------------
            # SCREENSHOT 1: Main Dashboard (Operations Overview)
            # -------------------------------------------------------------
            print("[*] Waiting for ScenarioPicker on Overview...")
            scenario_select = page.locator("select#scenario-select")
            scenario_select.wait_for(state="visible", timeout=15000)
            time.sleep(0.8)
            print("[*] Capturing Screenshot 1: dashboard.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "dashboard.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'dashboard.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 2: Run link_congestion and capture Diagnostic Report
            # -------------------------------------------------------------
            print("[*] Selecting link_congestion.json and running diagnosis...")
            scenario_select.select_option("link_congestion.json")
            time.sleep(0.5)
            run_btn = page.locator("button:has-text('Run Network Diagnosis')").first
            run_btn.click()
            page.wait_for_selector("text=Link utilization saturation", timeout=25000)
            time.sleep(1.0)

            print("[*] Navigating to Unified Diagnostic Report view...")
            page.locator("aside button:has-text('Unified Diagnostic Report')").first.click()
            time.sleep(1.2)
            print("[*] Capturing Screenshot 2: diagnostic-report.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "diagnostic-report.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'diagnostic-report.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 3: Evidence Provenance Table (Observation vs Hypothesis)
            # -------------------------------------------------------------
            print("[*] Scrolling to Corroborated Evidence Chains...")
            evidence_header = page.locator("text=Corroborated Evidence Chains").first
            if evidence_header.is_visible():
                evidence_header.scroll_into_view_if_needed()
                time.sleep(0.8)
            print("[*] Capturing Screenshot 3: evidence-provenance.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "evidence-provenance.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'evidence-provenance.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 4: Consensus Workspace & Agent Graph
            # -------------------------------------------------------------
            print("[*] Navigating to Consensus Workspace...")
            page.locator("aside button:has-text('Consensus Workspace')").first.click()
            time.sleep(1.2)
            print("[*] Capturing Screenshot 4: agent-orchestration.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "agent-orchestration.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'agent-orchestration.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 5: Network Topology & Blast Radius
            # -------------------------------------------------------------
            print("[*] Navigating to Topology & Blast Radius...")
            page.locator("aside button:has-text('Topology & Blast Radius')").first.click()
            time.sleep(1.2)
            print("[*] Capturing Screenshot 5: network-topology.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "network-topology.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'network-topology.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 6: Simulated Remediation & Audit Sandbox
            # -------------------------------------------------------------
            print("[*] Navigating to Simulated Remediation...")
            page.locator("aside button:has-text('Simulated Remediation')").first.click()
            time.sleep(1.2)
            print("[*] Capturing Screenshot 6: remediation-audit.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "remediation-audit.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'remediation-audit.png'}")

            # -------------------------------------------------------------
            # SCREENSHOT 7: Safe Abstention on Insufficient Data
            # -------------------------------------------------------------
            print("[*] Navigating back to Overview and running insufficient_data.json...")
            role_btn = page.locator("aside button:has-text('Network Engineer')").first
            if role_btn.is_visible():
                role_btn.click()
                time.sleep(0.8)

            scenario_select = page.locator("select#scenario-select")
            scenario_select.wait_for(state="visible", timeout=10000)
            scenario_select.select_option("insufficient_data.json")
            time.sleep(0.5)
            run_btn = page.locator("button:has-text('Run Network Diagnosis')").first
            run_btn.click()
            # Wait for diagnosis execution to finish
            time.sleep(4.0)

            print("[*] Navigating to Diagnostic Report for safe abstention...")
            page.locator("aside button:has-text('Unified Diagnostic Report')").first.click()
            time.sleep(1.2)
            print("[*] Capturing Screenshot 7: safe-abstention.png...")
            page.screenshot(path=str(README_ASSETS_DIR / "safe-abstention.png"))
            print(f"    Saved: {README_ASSETS_DIR / 'safe-abstention.png'}")

            browser.close()
            print("[+] All 7 genuine screenshots captured successfully!")

    finally:
        print("[*] Shutting down frontend and backend processes...")
        kill_proc(frontend_proc)
        kill_proc(orch_proc)
        subprocess.run(
            [VENV_PYTHON, "scripts/run_agents.py", "--stop"],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


if __name__ == "__main__":
    capture_all_screenshots()
