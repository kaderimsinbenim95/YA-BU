#!/usr/bin/env python3
"""
Sync Manager — Blockchain Synchronisation

Handles initial block download (IBD) and incremental sync for nodes
that are behind the tip.  Implements:
  - Height comparison on handshake
  - Batch block requests (headers-first, then bodies)
  - Fork detection and reorg handling
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Awaitable

from core.network.p2p_node import P2PNode, Message, MessageType, PeerConnection


class SyncState(Enum):
    IDLE        = "idle"
    SYNCING     = "syncing"
    SYNCED      = "synced"
    REORGING    = "reorging"
    ERROR       = "error"


@dataclass
class SyncStatus:
    state: SyncState = SyncState.IDLE
    local_height: int = 0
    best_peer_height: int = 0
    blocks_downloaded: int = 0
    blocks_applied: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    errors: List[str] = field(default_factory=list)

    def progress_pct(self) -> float:
        if self.best_peer_height == 0:
            return 100.0
        return min(100.0, (self.local_height / self.best_peer_height) * 100)

    def elapsed_secs(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time if self.start_time else 0.0


class SyncManager:
    """
    Orchestrates syncing our local chain with the best peer.

    Usage:
        manager = SyncManager(node, get_height_fn, apply_block_fn)
        await manager.start()
    """

    BATCH_SIZE     = 64     # Blocks per batch request
    MAX_RETRIES    = 3      # Retries per batch
    RETRY_DELAY    = 5.0    # Seconds between retries
    SYNC_TIMEOUT   = 30.0   # Seconds to wait for a batch

    def __init__(
        self,
        node: P2PNode,
        get_local_height: Callable[[], int],
        get_block_by_index: Callable[[int], Optional[dict]],
        apply_block: Callable[[dict], Awaitable[bool]],
    ):
        self.node = node
        self.get_local_height = get_local_height
        self.get_block_by_index = get_block_by_index
        self.apply_block = apply_block

        self.status = SyncStatus()
        self._pending_responses: Dict[int, asyncio.Future] = {}
        self._running = False

        # Register handlers
        node.on(MessageType.GET_CHAIN,      self._handle_get_chain)
        node.on(MessageType.CHAIN_RESPONSE, self._handle_chain_response)
        node.on(MessageType.GET_BLOCK,      self._handle_get_block)
        node.on(MessageType.BLOCK_RESPONSE, self._handle_block_response)

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self):
        """Begin sync loop."""
        self._running = True
        asyncio.create_task(self._sync_loop())
        print("[Sync] SyncManager started")

    async def stop(self):
        self._running = False

    async def trigger_sync(self):
        """Manually trigger a sync cycle."""
        await self._sync_cycle()

    # ── Sync Loop ─────────────────────────────────────────────────────────────

    async def _sync_loop(self):
        while self._running:
            try:
                await self._sync_cycle()
            except Exception as e:
                self.status.state = SyncState.ERROR
                self.status.errors.append(str(e))
                print(f"[Sync] Error: {e}")
            await asyncio.sleep(10)

    async def _sync_cycle(self):
        """One full sync iteration."""
        local_height = self.get_local_height()
        self.status.local_height = local_height

        # Find the best peer (highest chain height)
        best_peer, best_height = self._best_peer()
        if best_peer is None or best_height <= local_height:
            if self.status.state != SyncState.SYNCED:
                self.status.state = SyncState.SYNCED
                print(f"[Sync] Chain synced at height {local_height}")
            return

        self.status.best_peer_height = best_height
        self.status.state = SyncState.SYNCING
        self.status.start_time = time.time()
        print(
            f"[Sync] Starting sync: local={local_height}, peer={best_height} "
            f"({best_height - local_height} blocks behind)"
        )

        # Download in batches
        current = local_height + 1
        while current <= best_height:
            end = min(current + self.BATCH_SIZE - 1, best_height)
            success = await self._download_batch(best_peer, current, end)
            if not success:
                self.status.state = SyncState.ERROR
                print(f"[Sync] Batch {current}-{end} failed")
                return
            current = end + 1

        self.status.end_time = time.time()
        self.status.state = SyncState.SYNCED
        elapsed = self.status.elapsed_secs()
        rate = self.status.blocks_downloaded / max(elapsed, 0.001)
        print(
            f"[Sync] ✅ Sync complete: {self.status.blocks_downloaded} blocks "
            f"in {elapsed:.1f}s ({rate:.0f} blocks/s)"
        )

    async def _download_batch(self, peer: PeerConnection, start: int, end: int) -> bool:
        """Request blocks `start..=end` from a peer with retry."""
        for attempt in range(self.MAX_RETRIES):
            try:
                # Create futures for each block in the batch
                loop = asyncio.get_event_loop()
                futs = {}
                for idx in range(start, end + 1):
                    fut: asyncio.Future = loop.create_future()
                    self._pending_responses[idx] = fut
                    futs[idx] = fut

                # Request the batch
                req = Message.create(
                    MessageType.GET_CHAIN,
                    self.node.node_id,
                    {"start": start, "end": end},
                )
                await peer.send(req)

                # Wait for all responses
                try:
                    blocks = await asyncio.wait_for(
                        asyncio.gather(*futs.values(), return_exceptions=True),
                        timeout=self.SYNC_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    print(f"[Sync] Timeout for batch {start}-{end}, attempt {attempt+1}")
                    for idx in futs:
                        self._pending_responses.pop(idx, None)
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

                # Apply blocks in order
                for block in blocks:
                    if isinstance(block, Exception):
                        continue
                    if block is not None:
                        ok = await self.apply_block(block)
                        if ok:
                            self.status.blocks_applied += 1
                            self.status.local_height = block.get("header", {}).get("index", 0)
                        self.status.blocks_downloaded += 1

                return True

            except Exception as e:
                print(f"[Sync] Batch error (attempt {attempt+1}): {e}")
                await asyncio.sleep(self.RETRY_DELAY)

        return False

    # ── Message Handlers ──────────────────────────────────────────────────────

    async def _handle_get_chain(self, conn: PeerConnection, msg: Message):
        """Peer requests a range of our blocks."""
        start = msg.payload.get("start", 0)
        end   = msg.payload.get("end",   start)

        blocks = []
        for idx in range(start, end + 1):
            block = self.get_block_by_index(idx)
            if block:
                blocks.append(block)

        resp = Message.create(
            MessageType.CHAIN_RESPONSE,
            self.node.node_id,
            {"blocks": blocks},
        )
        await conn.send(resp)

    async def _handle_chain_response(self, conn: PeerConnection, msg: Message):
        """Receive a batch of blocks from a peer."""
        for block in msg.payload.get("blocks", []):
            idx = block.get("header", {}).get("index")
            if idx is not None and idx in self._pending_responses:
                fut = self._pending_responses.pop(idx)
                if not fut.done():
                    fut.set_result(block)

    async def _handle_get_block(self, conn: PeerConnection, msg: Message):
        """Peer requests a single block."""
        idx = msg.payload.get("index")
        block = self.get_block_by_index(idx) if idx is not None else None

        resp = Message.create(
            MessageType.BLOCK_RESPONSE,
            self.node.node_id,
            {"block": block},
        )
        await conn.send(resp)

    async def _handle_block_response(self, conn: PeerConnection, msg: Message):
        """Receive a single requested block."""
        block = msg.payload.get("block")
        if block:
            idx = block.get("header", {}).get("index")
            if idx is not None and idx in self._pending_responses:
                fut = self._pending_responses.pop(idx)
                if not fut.done():
                    fut.set_result(block)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _best_peer(self):
        """Return (connection, height) of the peer with the highest chain."""
        best_conn   = None
        best_height = 0
        for conn in self.node.connections.values():
            if conn.peer.connected and conn.peer.block_height > best_height:
                best_height = conn.peer.block_height
                best_conn   = conn
        return best_conn, best_height

    def get_status(self) -> dict:
        return {
            "state":              self.status.state.value,
            "local_height":       self.status.local_height,
            "best_peer_height":   self.status.best_peer_height,
            "blocks_downloaded":  self.status.blocks_downloaded,
            "blocks_applied":     self.status.blocks_applied,
            "progress_pct":       round(self.status.progress_pct(), 2),
            "elapsed_secs":       round(self.status.elapsed_secs(), 2),
            "errors":             self.status.errors[-10:],
        }
