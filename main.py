#!/usr/bin/env python3
"""
SatoshiOS-AI-Blockchain — Node Entry Point

Starts the REST API (port 8080) and WebSocket server (port 8081)
together in a single process.

Usage:
    python main.py              # start both servers
    python main.py --api-only   # REST API only
    python main.py --ws-only    # WebSocket server only
    python main.py --host 0.0.0.0 --api-port 8080 --ws-port 8081
"""

import argparse
import asyncio
import threading
import os
import sys


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _check_deps():
    missing = []
    try:
        import flask  # noqa: F401
    except ImportError:
        missing.append("flask")
    try:
        import websockets  # noqa: F401
    except ImportError:
        missing.append("websockets")
    if missing:
        print(f"[main] Missing packages: {', '.join(missing)}")
        print("[main] Run:  pip install -r requirements.txt")
        sys.exit(1)


def _start_rest_api(host: str, port: int):
    """Run Flask REST API in the current thread (blocking)."""
    from api.rest_api import create_app
    app = create_app()
    print(f"[API ] REST API → http://{host}:{port}")
    app.run(host=host, port=port, debug=False, use_reloader=False)


async def _start_websocket(host: str, port: int):
    """Run WebSocket server (async)."""
    from api.websocket_server import WebSocketServer
    server = WebSocketServer(host=host, port=port)
    await server.start()
    print(f"[WS  ] WebSocket  → ws://{host}:{port}")
    # Keep running until cancelled
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        await server.stop()


def _run_websocket_loop(host: str, port: int):
    """Run the asyncio event loop for the WebSocket server in a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_start_websocket(host, port))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SatoshiOS-AI-Blockchain Node")
    parser.add_argument("--host",     default="0.0.0.0",  help="Bind address")
    parser.add_argument("--api-port", default=8080, type=int, help="REST API port")
    parser.add_argument("--ws-port",  default=8081, type=int, help="WebSocket port")
    parser.add_argument("--api-only", action="store_true", help="Start REST API only")
    parser.add_argument("--ws-only",  action="store_true", help="Start WebSocket only")
    args = parser.parse_args()

    _check_deps()

    print("=" * 60)
    print("  SatoshiOS-AI-Blockchain  v1.0.0")
    print("=" * 60)

    start_api = not args.ws_only
    start_ws  = not args.api_only

    if start_ws:
        ws_thread = threading.Thread(
            target=_run_websocket_loop,
            args=(args.host, args.ws_port),
            daemon=True,
        )
        ws_thread.start()

    if start_api:
        # Flask blocks — run in main thread
        _start_rest_api(args.host, args.api_port)
    elif start_ws:
        # WS-only: keep the main thread alive
        try:
            while True:
                import time; time.sleep(1)
        except KeyboardInterrupt:
            pass

    print("\n[main] Shutting down.")


if __name__ == "__main__":
    main()
