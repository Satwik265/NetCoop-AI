"""Capture headless Playwright screenshots of the NetCoop AI dashboard."""

import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
DASHBOARD_DIST = PROJECT_ROOT / "dashboard" / "dist"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets"
PORT = 4173


def capture_screenshots() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not DASHBOARD_DIST.exists():
        print("Building dashboard first...")
        subprocess.run(["npm", "run", "build"], cwd=PROJECT_ROOT / "dashboard", check=True, shell=True)

    # Start local HTTP server
    server_proc = subprocess.Popen(
        ["python", "-m", "http.server", str(PORT), "--directory", str(DASHBOARD_DIST)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})

            url = f"http://127.0.0.1:{PORT}"
            page.goto(url, wait_until="networkidle")
            time.sleep(1.0)

            # 1. Dark Mode Dashboard Overview (Default)
            dark_path = OUTPUT_DIR / "dashboard_dark.png"
            page.screenshot(path=str(dark_path), full_page=False)
            print(f"Captured: {dark_path}")

            # 2. Light Mode Dashboard Overview
            # Click Theme Toggle
            theme_btn = page.query_selector('button[title*="Toggle Light"]')
            if theme_btn:
                theme_btn.click()
                time.sleep(0.5)
                light_path = OUTPUT_DIR / "dashboard_light.png"
                page.screenshot(path=str(light_path), full_page=False)
                print(f"Captured: {light_path}")
                # Switch back to dark
                theme_btn.click()
                time.sleep(0.3)

            # 3. Interoperability Inspector Tab
            interop_tab = page.query_selector('button:has-text("Interoperability Inspector")')
            if interop_tab:
                interop_tab.click()
                time.sleep(0.8)
                interop_path = OUTPUT_DIR / "interop_inspector.png"
                page.screenshot(path=str(interop_path), full_page=False)
                print(f"Captured: {interop_path}")

            # 4. Topology & Blast Radius View
            topo_tab = page.query_selector('button:has-text("Topology & Blast Radius")')
            if topo_tab:
                topo_tab.click()
                time.sleep(0.8)
                topo_path = OUTPUT_DIR / "agent_graph.png"
                page.screenshot(path=str(topo_path), full_page=False)
                print(f"Captured: {topo_path}")

            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    capture_screenshots()

