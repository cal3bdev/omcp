#!/usr/bin/env python3
"""Startup script for the Widget Store API example.

Starts the Widget Store API backend, OMCP server, and optionally the Chainlit UI.

Usage:
    # Start servers only
    uv run python examples/messy_api/start.py

    # Start servers + Chainlit UI
    uv run python examples/messy_api/start.py --ui
"""

from __future__ import annotations

import argparse
import atexit
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

processes: list[subprocess.Popen] = []


def cleanup():
    """Terminate all child processes."""
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()


def signal_handler(signum, frame):
    """Handle interrupt signals."""
    print("\n\nShutting down...")
    cleanup()
    sys.exit(0)


def start_process(name: str, cmd: list[str], port: int | None = None) -> subprocess.Popen:
    """Start a process and wait for it to be ready."""
    port_str = f" on port {port}" if port else ""
    print(f"Starting {name}{port_str}...")

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    processes.append(proc)

    time.sleep(2)

    if proc.poll() is not None:
        output = proc.stdout.read() if proc.stdout else ""
        print(f"ERROR: {name} failed to start:")
        print(output)
        sys.exit(1)

    print(f"  {name} started (PID: {proc.pid})")
    return proc


def main():
    parser = argparse.ArgumentParser(description="Start the Widget Store API example")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Also start the Chainlit web UI",
    )
    args = parser.parse_args()

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 50)
    print("Widget Store Demo - Startup Script")
    print("=" * 50)
    print()

    # Start Widget Store API backend
    api_proc = start_process(
        "Widget Store API",
        ["uv", "run", "uvicorn", "examples.messy_api.main:app", "--port", "8001"],
        8001,
    )

    # Start OMCP server
    omcp_proc = start_process(
        "OMCP Server",
        ["uv", "run", "omcp", "serve", "--config", "examples/messy_api/omcp.yaml"],
        9000,
    )

    # Optionally start Chainlit UI
    ui_proc = None
    if args.ui:
        ui_proc = start_process(
            "Chainlit UI",
            ["uv", "run", "chainlit", "run", "examples/messy_api/app.py", "--port", "8002"],
            8002,
        )

    print()
    print("=" * 50)
    print("All servers are running!")
    print("=" * 50)
    print()
    print("  Widget API: http://localhost:8001")
    print("  OMCP:       http://localhost:9000")
    if args.ui:
        print("  Chainlit:   http://localhost:8002  <- Open this in your browser!")
    print()
    if not args.ui:
        print("To start the web UI, restart with --ui flag:")
        print("  uv run python examples/messy_api/start.py --ui")
    print()
    print("Press Ctrl+C to stop all servers")
    print("-" * 50)
    print()

    monitored = [("API", api_proc), ("OMCP", omcp_proc)]
    if ui_proc:
        monitored.append(("UI", ui_proc))

    try:
        while True:
            for name, proc in monitored:
                if proc.poll() is not None:
                    print(f"\n{name} process exited unexpectedly!")
                    cleanup()
                    sys.exit(1)

                if proc.stdout:
                    line = proc.stdout.readline()
                    if line:
                        print(f"[{name:4}] {line.rstrip()}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
