#!/usr/bin/env python3
"""Startup script for the Auth API example.

Starts the Notes API backend, OMCP server, and optionally the Chainlit UI.

Usage:
    # Start servers only
    uv run python examples/auth_api/start.py

    # Start servers + Chainlit UI
    uv run python examples/auth_api/start.py --ui

Then in another terminal (if not using --ui):
    uv run python examples/auth_api/client.py --user alice
"""

from __future__ import annotations

import argparse
import atexit
import signal
import subprocess
import sys
import time
from pathlib import Path

# Get project root (two levels up from this script)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Process handles
processes: list[subprocess.Popen] = []


def cleanup():
    """Terminate all child processes."""
    for proc in processes:
        if proc.poll() is None:  # Still running
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

    # Wait for startup
    time.sleep(2)

    if proc.poll() is not None:
        # Process died, show output
        output = proc.stdout.read() if proc.stdout else ""
        print(f"ERROR: {name} failed to start:")
        print(output)
        sys.exit(1)

    print(f"  {name} started (PID: {proc.pid})")
    return proc


def main():
    parser = argparse.ArgumentParser(description="Start the Auth API example")
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Also start the Chainlit web UI",
    )
    args = parser.parse_args()

    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 50)
    print("Auth API Example - Startup Script")
    print("=" * 50)
    print()

    # Start Notes API backend
    api_proc = start_process(
        "Notes API",
        ["uv", "run", "uvicorn", "examples.auth_api.main:app", "--port", "8080"],
        8080,
    )

    # Start OMCP server
    omcp_proc = start_process(
        "OMCP Server",
        ["uv", "run", "omcp", "serve", "--config", "examples/auth_api/omcp.yaml"],
        9000,
    )

    # Optionally start Chainlit UI
    ui_proc = None
    if args.ui:
        ui_proc = start_process(
            "Chainlit UI",
            ["uv", "run", "chainlit", "run", "examples/auth_api/app.py", "--port", "8000"],
            8000,
        )

    print()
    print("=" * 50)
    print("All servers are running!")
    print("=" * 50)
    print()
    print("  Notes API:  http://localhost:8080")
    print("  OMCP:       http://localhost:9000")
    if args.ui:
        print("  Chainlit:   http://localhost:8000  <- Open this in your browser!")
    print()
    if not args.ui:
        print("To test, run in another terminal:")
        print("  uv run chainlit run examples/auth_api/app.py  # Web UI")
        print("  uv run python examples/auth_api/client.py --user alice  # Terminal")
        print()
        print("Or restart with --ui flag to auto-launch the web UI:")
        print("  uv run python examples/auth_api/start.py --ui")
    print()
    print("Press Ctrl+C to stop all servers")
    print("-" * 50)
    print()

    # Build process list for monitoring
    monitored = [("API", api_proc), ("OMCP", omcp_proc)]
    if ui_proc:
        monitored.append(("UI", ui_proc))

    # Stream combined output
    try:
        while True:
            # Check if processes are still running
            for name, proc in monitored:
                if proc.poll() is not None:
                    print(f"\n{name} process exited unexpectedly!")
                    cleanup()
                    sys.exit(1)

                # Read available output (non-blocking would be better, but this works)
                if proc.stdout:
                    line = proc.stdout.readline()
                    if line:
                        print(f"[{name:4}] {line.rstrip()}")

            time.sleep(0.1)

    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
