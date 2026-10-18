#!/usr/bin/env python3
"""
Gossip Protocol — Block and Transaction Propagation

Implements epidemic/gossip-style dissemination of new blocks and
transactions across the P2P network using a push-pull hybrid strategy.
"""

import asyncio
import time
import json
import hashlib
from typing import Dict, List, Set, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
from enum import Enum

from core.network.p2p_node import P2PNode, Message, MessageType, PeerConnection


# ─── Gossip Message Types ─────────────────────────────────────────────────────

class GossipEvent(Enum):
    ANNOUNCE_BLOCK  = "announce_block"   # "I have block X"
    ANNOUNCE_TX     = "announce_tx"      # "I have tx X"
    REQUEST_BLOCK   = "request_block"    # "Send me block X"
    REQUEST_TX      = "request_tx"       # "Send me tx X"
    BLOCK_DATA      = "block_data"       # Actual block payload
    TX_DATA         = "tx_data"          # Actual transaction payload
    INV             = "inv"              # Inventory: list of block/tx hashes


# ─── Gossip State ─────────────────────────────────────────────────────────────

@dataclass
class GossipStats:
    blocks_announced: int = 0
    blocks_received:  int = 0
    txs_announced:    int = 0
    txs_received:     int = 0
    duplicate_skipped: int = 0


# ─── GossipProtocol ───────────────────────────────────────────────────────────

class GossipProtocol:
    """
    Gossip-based block and transaction propagation.

    Uses the **push-pull** model:
    - Push: announce hash to all peers (INV message)
    - Pull: peers who lack the item request it (REQUEST_BLOCK / REQUEST_TX)

    This avoids redundant full-payload floods while ensuring every node
    eventually receives every item.
    """

    GOSSIP_FANOUT = 8      # Max peers to push to per round
    MAX_INVENTORY = 50_000  # Hashes to remember (dedup)

    def __init__(self, node: P2PNode, chain_height_fn: Optional[Callable[[], int]] = None):
        self.node = node
        self.chain_height_fn = chain_height_fn or (lambda: 0)

        # Known inventories (hash → timestamp)
        self._known_blocks: Dict[str, float] = {}
        self._known_txs:    Dict[str, float] = {}

        # Callbacks for application layer
        self._on_block: Optional[Callable] = None
        self._on_tx:    Optional[Callable] = None

        self.stats = GossipStats()

        # Register gossip message handlers on the node
        self._register_handlers()

    def on_block(self, handler: Callable[[dict], Awaitable[None]]):
        """Register callback for received blocks."""
        self._on_block = handler

    def on_transaction(self, handler: Callable[[dict], Awaitable[None]]):
        """Register callback for received transactions."""
        self._on_tx = handler

    # ── Public API ────────────────────────────────────────────────────────────

    async def announce_block(self, block: dict):
        """
        Propagate a new block to the network.

        Sends an INV message (hash only) to all connected peers.
        Peers who lack the block will request the full payload.
        """
        block_hash = block.get("hash", _hash_dict(block))

        if block_hash in self._known_blocks:
            return  # Already propagated

        self._known_blocks[block_hash] = time.time()
        self._trim_inventory(self._known_blocks)
        self.stats.blocks_announced += 1

        msg = Message.create(
            MessageType.NEW_BLOCK,
            self.node.node_id,
            {
                "event": GossipEvent.ANNOUNCE_BLOCK.value,
                "hash": block_hash,
                "height": block.get("header", {}).get("index", 0),
            },
        )
        peers = self._select_fanout_peers()
        for conn in peers:
            await conn.send(msg)
        print(f"[Gossip] Announced block {block_hash[:12]} to {len(peers)} peers")

    async def broadcast_block(self, block: dict):
        """
        Push the full block payload directly to peers (used during initial sync
        or when a peer explicitly requests).
        """
        block_hash = block.get("hash", _hash_dict(block))
        self._known_blocks[block_hash] = time.time()

        msg = Message.create(
            MessageType.NEW_BLOCK,
            self.node.node_id,
            {
                "event": GossipEvent.BLOCK_DATA.value,
                "block": block,
            },
        )
        await self.node.broadcast(msg)

    async def announce_transaction(self, tx: dict):
        """Propagate a new transaction hash to peers."""
        tx_id = tx.get("tx_id", _hash_dict(tx))

        if tx_id in self._known_txs:
            return

        self._known_txs[tx_id] = time.time()
        self._trim_inventory(self._known_txs)
        self.stats.txs_announced += 1

        msg = Message.create(
            MessageType.NEW_TRANSACTION,
            self.node.node_id,
            {
                "event": GossipEvent.ANNOUNCE_TX.value,
                "tx_id": tx_id,
            },
        )
        peers = self._select_fanout_peers()
        for conn in peers:
            await conn.send(msg)

    async def send_inventory(self, peer_conn: PeerConnection, block_hashes: List[str], tx_ids: List[str]):
        """Send an INV message listing what we have."""
        msg = Message.create(
            MessageType.NEW_BLOCK,
            self.node.node_id,
            {
                "event": GossipEvent.INV.value,
                "blocks": block_hashes,
                "txs": tx_ids,
            },
        )
        await peer_conn.send(msg)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _register_handlers(self):
        self.node.on(MessageType.NEW_BLOCK,       self._handle_block_message)
        self.node.on(MessageType.NEW_TRANSACTION, self._handle_tx_message)

    async def _handle_block_message(self, conn: PeerConnection, msg: Message):
        event = msg.payload.get("event", GossipEvent.BLOCK_DATA.value)

        if event == GossipEvent.ANNOUNCE_BLOCK.value:
            block_hash = msg.payload.get("hash", "")
            if block_hash in self._known_blocks:
                self.stats.duplicate_skipped += 1
                return

            # Request the full block
            req = Message.create(
                MessageType.GET_BLOCK,
                self.node.node_id,
                {
                    "event": GossipEvent.REQUEST_BLOCK.value,
                    "hash": block_hash,
                },
            )
            await conn.send(req)

        elif event == GossipEvent.BLOCK_DATA.value:
            block = msg.payload.get("block", {})
            block_hash = block.get("hash", _hash_dict(block))

            if block_hash in self._known_blocks:
                self.stats.duplicate_skipped += 1
                return

            self._known_blocks[block_hash] = time.time()
            self.stats.blocks_received += 1
            print(f"[Gossip] Received block {block_hash[:12]} from {conn.peer.peer_id}")

            # Forward to application
            if self._on_block:
                await self._on_block(block)

            # Re-announce to other peers (propagation)
            announce = Message.create(
                MessageType.NEW_BLOCK,
                self.node.node_id,
                {
                    "event": GossipEvent.ANNOUNCE_BLOCK.value,
                    "hash": block_hash,
                    "height": block.get("header", {}).get("index", 0),
                },
            )
            peers = self._select_fanout_peers(exclude=conn.peer.peer_id)
            for peer_conn in peers:
                await peer_conn.send(announce)

        elif event == GossipEvent.INV.value:
            # Process inventory list
            for bh in msg.payload.get("blocks", []):
                if bh not in self._known_blocks:
                    req = Message.create(
                        MessageType.GET_BLOCK, self.node.node_id,
                        {"event": GossipEvent.REQUEST_BLOCK.value, "hash": bh}
                    )
                    await conn.send(req)

    async def _handle_tx_message(self, conn: PeerConnection, msg: Message):
        event = msg.payload.get("event", GossipEvent.TX_DATA.value)

        if event == GossipEvent.ANNOUNCE_TX.value:
            tx_id = msg.payload.get("tx_id", "")
            if tx_id in self._known_txs:
                self.stats.duplicate_skipped += 1
                return
            # Request full tx
            req = Message.create(
                MessageType.GET_BLOCK, self.node.node_id,
                {"event": GossipEvent.REQUEST_TX.value, "tx_id": tx_id}
            )
            await conn.send(req)

        elif event == GossipEvent.TX_DATA.value:
            tx = msg.payload.get("tx", {})
            tx_id = tx.get("tx_id", _hash_dict(tx))

            if tx_id in self._known_txs:
                self.stats.duplicate_skipped += 1
                return

            self._known_txs[tx_id] = time.time()
            self.stats.txs_received += 1

            if self._on_tx:
                await self._on_tx(tx)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _select_fanout_peers(self, exclude: Optional[str] = None) -> List[PeerConnection]:
        """Pick up to GOSSIP_FANOUT connected peers, optionally excluding one."""
        import random
        peers = [
            c for c in self.node.connections.values()
            if c.peer.connected and c.peer.peer_id != exclude
        ]
        return random.sample(peers, min(self.GOSSIP_FANOUT, len(peers)))

    def _trim_inventory(self, inv: Dict[str, float]):
        """Evict oldest entries when inventory exceeds limit."""
        if len(inv) > self.MAX_INVENTORY:
            oldest = sorted(inv.items(), key=lambda x: x[1])
            for k, _ in oldest[:len(inv) - self.MAX_INVENTORY]:
                del inv[k]

    def get_stats(self) -> dict:
        return asdict(self.stats)


def _hash_dict(d: dict) -> str:
    raw = json.dumps(d, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()
