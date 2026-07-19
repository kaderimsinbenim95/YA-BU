#!/usr/bin/env python3
"""
P2P Node — Peer-to-Peer Network Layer

Manages peer discovery, connection lifecycle, and message routing
for the SatoshiOS blockchain network.
"""

import asyncio
import json
import hashlib
import time
import uuid
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Set, Callable, Awaitable


class MessageType(Enum):
    """P2P message types"""
    HANDSHAKE        = "handshake"
    HANDSHAKE_ACK    = "handshake_ack"
    PING             = "ping"
    PONG             = "pong"
    GET_PEERS        = "get_peers"
    PEERS            = "peers"
    NEW_BLOCK        = "new_block"
    GET_BLOCK        = "get_block"
    BLOCK_RESPONSE   = "block_response"
    NEW_TRANSACTION  = "new_transaction"
    GET_CHAIN        = "get_chain"
    CHAIN_RESPONSE   = "chain_response"
    DISCONNECT       = "disconnect"


@dataclass
class PeerInfo:
    """Metadata for a known peer"""
    peer_id: str
    host: str
    port: int
    version: str = "1.0"
    last_seen: float = 0.0
    connected: bool = False
    latency_ms: float = 0.0
    block_height: int = 0

    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Message:
    """A P2P network message"""
    msg_id: str
    msg_type: str
    sender_id: str
    payload: dict
    timestamp: float

    @staticmethod
    def create(msg_type: MessageType, sender_id: str, payload: dict) -> "Message":
        return Message(
            msg_id=str(uuid.uuid4()),
            msg_type=msg_type.value,
            sender_id=sender_id,
            payload=payload,
            timestamp=time.time(),
        )

    def encode(self) -> bytes:
        return (json.dumps(asdict(self)) + "\n").encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> "Message":
        d = json.loads(data.decode("utf-8").strip())
        return Message(**d)


# ─── Connection ───────────────────────────────────────────────────────────────

class PeerConnection:
    """Wraps an asyncio StreamReader/StreamWriter pair for one peer."""

    def __init__(
        self,
        peer_info: PeerInfo,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        on_message: Callable[["PeerConnection", Message], Awaitable[None]],
        on_disconnect: Callable[["PeerConnection"], Awaitable[None]],
    ):
        self.peer = peer_info
        self.reader = reader
        self.writer = writer
        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._running = False

    async def send(self, message: Message):
        """Send a message to the peer."""
        try:
            self.writer.write(message.encode())
            await self.writer.drain()
        except Exception as e:
            print(f"[P2P] Send error to {self.peer.address()}: {e}")
            await self.close()

    async def start_receiving(self):
        """Start reading loop in background."""
        self._running = True
        try:
            while self._running:
                line = await asyncio.wait_for(self.reader.readline(), timeout=60.0)
                if not line:
                    break
                try:
                    msg = Message.decode(line)
                    self.peer.last_seen = time.time()
                    await self._on_message(self, msg)
                except Exception as e:
                    print(f"[P2P] Parse error from {self.peer.address()}: {e}")
        except asyncio.TimeoutError:
            print(f"[P2P] Timeout on {self.peer.address()}, disconnecting")
        except Exception as e:
            print(f"[P2P] Connection error with {self.peer.address()}: {e}")
        finally:
            await self.close()

    async def close(self):
        if self._running:
            self._running = False
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.peer.connected = False
            await self._on_disconnect(self)


# ─── P2PNode ──────────────────────────────────────────────────────────────────

class P2PNode:
    """
    Full peer-to-peer node.

    * Listens for inbound connections on `host:port`
    * Connects to bootstrap peers on startup
    * Routes incoming messages to registered handlers
    * Maintains a peer table with health tracking
    """

    MAX_PEERS = 50
    PING_INTERVAL = 30  # seconds

    def __init__(self, host: str, port: int, node_id: Optional[str] = None):
        self.host = host
        self.port = port
        self.node_id = node_id or hashlib.sha256(f"{host}:{port}:{time.time()}".encode()).hexdigest()[:16]
        self.version = "1.0"

        # Active connections
        self.connections: Dict[str, PeerConnection] = {}
        # Known peer table (peer_id → PeerInfo)
        self.peers: Dict[str, PeerInfo] = {}
        # Message handlers (msg_type → coroutine)
        self._handlers: Dict[str, Callable] = {}
        # Seen message IDs (dedup)
        self._seen_messages: Set[str] = set()

        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False

        # Register built-in handlers
        self._register_builtin_handlers()
        print(f"[P2P] Node created: id={self.node_id}, address={host}:{port}")

    # ── Built-in Handlers ─────────────────────────────────────────────────────

    def _register_builtin_handlers(self):
        self.on(MessageType.HANDSHAKE,       self._handle_handshake)
        self.on(MessageType.HANDSHAKE_ACK,   self._handle_handshake_ack)
        self.on(MessageType.PING,            self._handle_ping)
        self.on(MessageType.PONG,            self._handle_pong)
        self.on(MessageType.GET_PEERS,       self._handle_get_peers)
        self.on(MessageType.PEERS,           self._handle_peers)
        self.on(MessageType.DISCONNECT,      self._handle_disconnect)

    async def _handle_handshake(self, conn: PeerConnection, msg: Message):
        p = msg.payload
        conn.peer.peer_id   = p.get("peer_id", conn.peer.peer_id)
        conn.peer.version   = p.get("version", "1.0")
        conn.peer.block_height = p.get("block_height", 0)
        conn.peer.connected = True
        self.peers[conn.peer.peer_id] = conn.peer

        ack = Message.create(MessageType.HANDSHAKE_ACK, self.node_id, {
            "peer_id": self.node_id,
            "version": self.version,
        })
        await conn.send(ack)
        print(f"[P2P] Handshake complete with peer {conn.peer.peer_id}")

    async def _handle_handshake_ack(self, conn: PeerConnection, msg: Message):
        conn.peer.peer_id = msg.payload.get("peer_id", conn.peer.peer_id)
        conn.peer.connected = True
        self.peers[conn.peer.peer_id] = conn.peer
        print(f"[P2P] Handshake ACK from {conn.peer.peer_id}")

    async def _handle_ping(self, conn: PeerConnection, msg: Message):
        pong = Message.create(MessageType.PONG, self.node_id, {
            "echo": msg.msg_id,
        })
        await conn.send(pong)

    async def _handle_pong(self, conn: PeerConnection, msg: Message):
        sent_ts = msg.payload.get("sent_ts", time.time())
        conn.peer.latency_ms = (time.time() - sent_ts) * 1000

    async def _handle_get_peers(self, conn: PeerConnection, msg: Message):
        peer_list = [
            {"peer_id": p.peer_id, "host": p.host, "port": p.port}
            for p in list(self.peers.values())[:20]
        ]
        resp = Message.create(MessageType.PEERS, self.node_id, {"peers": peer_list})
        await conn.send(resp)

    async def _handle_peers(self, conn: PeerConnection, msg: Message):
        for peer_data in msg.payload.get("peers", []):
            pid = peer_data.get("peer_id", "")
            if pid and pid not in self.peers and pid != self.node_id:
                info = PeerInfo(
                    peer_id=pid,
                    host=peer_data["host"],
                    port=peer_data["port"],
                )
                self.peers[pid] = info
                print(f"[P2P] Discovered new peer: {info.address()}")

    async def _handle_disconnect(self, conn: PeerConnection, msg: Message):
        await conn.close()

    # ── Public API ────────────────────────────────────────────────────────────

    def on(self, msg_type: MessageType, handler: Callable):
        """Register a message handler."""
        self._handlers[msg_type.value] = handler

    async def start(self):
        """Start listening for inbound connections."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_inbound, self.host, self.port
        )
        print(f"[P2P] Listening on {self.host}:{self.port}")
        asyncio.create_task(self._ping_loop())

    async def stop(self):
        """Graceful shutdown."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for conn in list(self.connections.values()):
            await conn.close()
        print("[P2P] Node stopped")

    async def connect(self, host: str, port: int) -> bool:
        """Open an outbound connection to a peer."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10.0
            )
            peer_info = PeerInfo(peer_id="", host=host, port=port)
            conn = PeerConnection(
                peer_info, reader, writer,
                self._dispatch, self._on_disconnect
            )
            # Temporary key until handshake
            tmp_key = f"{host}:{port}"
            self.connections[tmp_key] = conn

            asyncio.create_task(conn.start_receiving())

            # Send handshake
            hs = Message.create(MessageType.HANDSHAKE, self.node_id, {
                "peer_id": self.node_id,
                "version": self.version,
                "block_height": 0,
            })
            await conn.send(hs)
            print(f"[P2P] Connected to {host}:{port}")
            return True
        except Exception as e:
            print(f"[P2P] Connection failed to {host}:{port}: {e}")
            return False

    async def broadcast(self, message: Message, exclude: Optional[str] = None):
        """Broadcast message to all connected peers."""
        for conn in list(self.connections.values()):
            if conn.peer.peer_id != exclude:
                await conn.send(message)

    async def send_to(self, peer_id: str, message: Message) -> bool:
        """Send message to specific peer."""
        conn = self.connections.get(peer_id)
        if conn:
            await conn.send(message)
            return True
        return False

    def connected_peers(self) -> List[PeerInfo]:
        return [c.peer for c in self.connections.values() if c.peer.connected]

    def peer_count(self) -> int:
        return len(self.connected_peers())

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _handle_inbound(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        host, port = addr[0], addr[1]
        print(f"[P2P] Inbound connection from {host}:{port}")

        peer_info = PeerInfo(peer_id="", host=host, port=port)
        conn = PeerConnection(peer_info, reader, writer, self._dispatch, self._on_disconnect)
        tmp_key = f"{host}:{port}"
        self.connections[tmp_key] = conn
        await conn.start_receiving()

    async def _dispatch(self, conn: PeerConnection, msg: Message):
        """Route message to the registered handler."""
        if msg.msg_id in self._seen_messages:
            return
        self._seen_messages.add(msg.msg_id)
        # Prevent memory leak
        if len(self._seen_messages) > 10_000:
            self._seen_messages = set(list(self._seen_messages)[-5000:])

        handler = self._handlers.get(msg.msg_type)
        if handler:
            await handler(conn, msg)
        else:
            print(f"[P2P] Unhandled message type: {msg.msg_type}")

    async def _on_disconnect(self, conn: PeerConnection):
        addr = f"{conn.peer.host}:{conn.peer.port}"
        self.connections.pop(conn.peer.peer_id, None)
        self.connections.pop(addr, None)
        if conn.peer.peer_id in self.peers:
            self.peers[conn.peer.peer_id].connected = False
        print(f"[P2P] Peer disconnected: {addr}")

    async def _ping_loop(self):
        """Periodically ping connected peers."""
        while self._running:
            await asyncio.sleep(self.PING_INTERVAL)
            for conn in list(self.connections.values()):
                if conn.peer.connected:
                    ping = Message.create(MessageType.PING, self.node_id, {
                        "sent_ts": time.time()
                    })
                    await conn.send(ping)

    def stats(self) -> dict:
        return {
            "node_id": self.node_id,
            "address": f"{self.host}:{self.port}",
            "connected_peers": self.peer_count(),
            "known_peers": len(self.peers),
            "version": self.version,
        }
