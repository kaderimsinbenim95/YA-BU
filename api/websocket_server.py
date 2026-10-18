#!/usr/bin/env python3
"""
WebSocket Server — Real-Time Block and Event Streaming

Broadcasts new blocks, transactions, and threat events to connected
WebSocket clients using `websockets`.

Run with:  python -m api.websocket_server
"""

import asyncio
import json
import time
import hashlib
from typing import Set, Dict, Any, Optional, Callable

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    WebSocketServerProtocol = Any  # type: ignore


# ─── Event Types ──────────────────────────────────────────────────────────────

class EventType:
    NEW_BLOCK       = "new_block"
    NEW_TRANSACTION = "new_transaction"
    THREAT_ALERT    = "threat_alert"
    CONSENSUS_CHANGE = "consensus_change"
    PEER_CONNECTED  = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    SYNC_PROGRESS   = "sync_progress"
    SUBSCRIBE_OK    = "subscribe_ok"
    PING            = "ping"
    PONG            = "pong"
    ERROR           = "error"


# ─── Event Builder ────────────────────────────────────────────────────────────

def make_event(event_type: str, payload: dict) -> str:
    return json.dumps({
        "type":      event_type,
        "timestamp": int(time.time()),
        "payload":   payload,
    })


# ─── Subscription Channels ───────────────────────────────────────────────────

CHANNELS = {
    "blocks",
    "transactions",
    "threats",
    "consensus",
    "peers",
    "sync",
    "all",
}


# ─── WebSocketServer ──────────────────────────────────────────────────────────

class WebSocketServer:
    """
    WebSocket server for real-time event streaming.

    Clients subscribe to one or more channels via:
        {"action": "subscribe", "channels": ["blocks", "transactions"]}

    The server pushes JSON events to subscribers of matching channels.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8081):
        self.host = host
        self.port = port

        # client → set of subscribed channels
        self._clients: Dict[Any, Set[str]] = {}
        # Total event counters
        self._stats = {
            "events_sent":        0,
            "clients_connected":  0,
            "clients_total":      0,
        }
        self._server = None

    # ── Connection Handling ───────────────────────────────────────────────────

    async def _handler(self, ws: Any, path: str = "/"):
        """Handle a new WebSocket connection."""
        self._clients[ws] = set()
        self._stats["clients_connected"] += 1
        self._stats["clients_total"]     += 1
        print(f"[WS] Client connected from {ws.remote_address} (total: {self._stats['clients_connected']})")

        try:
            async for raw_message in ws:
                await self._handle_message(ws, raw_message)
        except Exception as e:
            print(f"[WS] Client error: {e}")
        finally:
            self._clients.pop(ws, None)
            self._stats["clients_connected"] -= 1
            print(f"[WS] Client disconnected (remaining: {self._stats['clients_connected']})")

    async def _handle_message(self, ws: Any, raw: str):
        """Process a message from a client."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send(make_event(EventType.ERROR, {"message": "Invalid JSON"}))
            return

        action = msg.get("action", "")

        if action == "subscribe":
            channels = set(msg.get("channels", ["all"]))
            valid = channels & CHANNELS
            invalid = channels - CHANNELS
            self._clients[ws] |= valid
            await ws.send(make_event(EventType.SUBSCRIBE_OK, {
                "subscribed": list(valid),
                "invalid":    list(invalid),
            }))
            print(f"[WS] Client subscribed to: {valid}")

        elif action == "unsubscribe":
            channels = set(msg.get("channels", []))
            self._clients[ws] -= channels
            await ws.send(make_event(EventType.SUBSCRIBE_OK, {
                "subscribed": list(self._clients[ws]),
            }))

        elif action == "ping":
            await ws.send(make_event(EventType.PONG, {"echo": msg.get("id", "")}))

        elif action == "get_stats":
            await ws.send(make_event("stats", self._stats))

        else:
            await ws.send(make_event(EventType.ERROR, {
                "message": f"Unknown action: {action}",
            }))

    # ── Event Broadcasting ────────────────────────────────────────────────────

    async def broadcast(self, channel: str, event_type: str, payload: dict):
        """
        Send an event to all clients subscribed to `channel` or `all`.
        Dead connections are cleaned up automatically.
        """
        message = make_event(event_type, payload)
        dead    = set()

        for ws, channels in list(self._clients.items()):
            if channel in channels or "all" in channels:
                try:
                    await ws.send(message)
                    self._stats["events_sent"] += 1
                except Exception:
                    dead.add(ws)

        for ws in dead:
            self._clients.pop(ws, None)

    async def broadcast_new_block(self, block: dict):
        """Notify all block subscribers of a new block."""
        payload = {
            "hash":   block.get("hash", ""),
            "index":  block.get("header", {}).get("index", 0),
            "txs":    len(block.get("transactions", [])),
            "miner":  block.get("header", {}).get("miner", ""),
            "ts":     block.get("header", {}).get("timestamp", 0),
        }
        await self.broadcast("blocks", EventType.NEW_BLOCK, payload)

    async def broadcast_new_transaction(self, tx: dict):
        """Notify transaction subscribers."""
        payload = {
            "tx_id":  tx.get("tx_id", ""),
            "from":   tx.get("from", ""),
            "to":     tx.get("to", ""),
            "amount": tx.get("amount", 0),
            "status": "pending",
        }
        await self.broadcast("transactions", EventType.NEW_TRANSACTION, payload)

    async def broadcast_threat_alert(self, threat: dict):
        """Notify threat subscribers of a security event."""
        await self.broadcast("threats", EventType.THREAT_ALERT, threat)

    async def broadcast_consensus_change(self, consensus_type: str, health: float):
        """Notify consensus subscribers of a mode switch."""
        await self.broadcast("consensus", EventType.CONSENSUS_CHANGE, {
            "consensus_type": consensus_type,
            "network_health": round(health, 2),
        })

    async def broadcast_sync_progress(self, local: int, best: int):
        """Notify sync subscribers of sync progress."""
        pct = round((local / max(best, 1)) * 100, 1)
        await self.broadcast("sync", EventType.SYNC_PROGRESS, {
            "local_height": local,
            "best_height":  best,
            "progress_pct": pct,
        })

    # ── Server Lifecycle ──────────────────────────────────────────────────────

    async def start(self):
        """Start listening for WebSocket connections."""
        if not WS_AVAILABLE:
            print("[WS] 'websockets' package not installed. Run: pip install websockets")
            return

        self._server = await websockets.serve(self._handler, self.host, self.port)
        print(f"[WS] WebSocket server listening on ws://{self.host}:{self.port}")

    async def stop(self):
        """Graceful shutdown."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        print("[WS] WebSocket server stopped")

    def stats(self) -> dict:
        return {**self._stats, "host": self.host, "port": self.port}


# ─── Entry Point ─────────────────────────────────────────────────────────────

async def _demo():
    """Demo: start server and send synthetic events every 5 seconds."""
    server = WebSocketServer()
    await server.start()

    print("[WS] Demo mode: broadcasting synthetic events every 5 seconds")
    block_index = 0

    try:
        while True:
            await asyncio.sleep(5)
            block_index += 1
            fake_hash = hashlib.sha256(f"block{block_index}".encode()).hexdigest()

            await server.broadcast_new_block({
                "hash": fake_hash,
                "header": {"index": block_index, "miner": "demo_miner", "timestamp": int(time.time())},
                "transactions": [],
            })
            print(f"[WS] Broadcast block #{block_index}")

    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(_demo())
