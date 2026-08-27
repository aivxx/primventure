from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from .store import ROOT


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="primventure",
        description="Enter the local OpenUSD certification crawl.",
    )
    result.add_argument("--api-only", action="store_true", help="Run only the FastAPI server.")
    result.add_argument("--no-browser", action="store_true", help="Do not open a browser tab.")
    result.add_argument("--port", type=int, default=8000, help="API port (default: 8000).")
    result.add_argument("--web-port", type=int, default=5173, help="Vite port (default: 5173).")
    return result


def main() -> None:
    args = parser().parse_args()
    web_dir = ROOT / "game" / "web"
    api_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "primventure.api:app",
        "--app-dir",
        str(ROOT / "game" / "server"),
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--reload",
        "--reload-dir",
        str(ROOT / "game" / "server"),
    ]
    processes = [subprocess.Popen(api_command, cwd=ROOT)]
    url = f"http://127.0.0.1:{args.port}"

    if not args.api_only:
        if shutil.which("npm") is None:
            processes[0].terminate()
            raise SystemExit("npm is required for the dungeon UI. Use --api-only for the server.")
        if not (web_dir / "node_modules").exists():
            print("Installing dungeon UI dependencies…")
            install = subprocess.run(["npm", "install"], cwd=web_dir)
            if install.returncode:
                processes[0].terminate()
                raise SystemExit("npm install failed.")
        env = os.environ.copy()
        env["VITE_API_URL"] = f"http://127.0.0.1:{args.port}"
        processes.append(
            subprocess.Popen(
                ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(args.web_port)],
                cwd=web_dir,
                env=env,
            )
        )
        url = f"http://127.0.0.1:{args.web_port}"

    def stop(_signum: int | None = None, _frame: object | None = None) -> None:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"\nSYSTEM ONLINE — enter the Composition at {url}")
    print("This server executes submitted Python. It is intentionally bound to localhost.\n")
    if not args.no_browser:
        time.sleep(1)
        webbrowser.open(url)
    try:
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    finally:
        stop()
    failed = next((process.returncode for process in processes if process.returncode), 0)
    raise SystemExit(failed)


if __name__ == "__main__":
    main()

