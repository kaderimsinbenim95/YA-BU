#!/usr/bin/env python3
"""
Mempool — Pending Transaction Pool

Manages unconfirmed transactions with priority queuing, fee-based ordering,
duplicate detection, nonce gap checking, and expiry eviction.
"""

import time
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PendingTransaction:
    """A transaction waiting to be mined."""
    tx_id:      str
    from_addr:  str
    to_addr:    str
    amount:     int
    gas_price:  int           # Higher gas_price = higher priority
    gas_limit:  int
    nonce:      int
    data:       bytes = field(default_factory=bytes)
    timestamp:  float = field(default_factory=time.time)
    raw:        dict = field(default_factory=dict)

    def fee(self) -> int:
        return self.gas_price * self.gas_limit

    # Comparison for the min-heap (negate gas_price for max-heap behaviour)
    def __lt__(self, other: "PendingTransaction") -> bool:
        return self.gas_price > other.gas_price  # Higher price = higher priority


@dataclass
class MempoolStats:
    total_added:   int = 0
    total_evicted: int = 0
    total_mined:   int = 0
    duplicates:    int = 0
    nonce_gaps:    int = 0


class Mempool:
    """
    Transaction pool with:
    - O(log n) priority-queue insertion and extraction
    - Per-sender nonce ordering
    - Configurable capacity and TTL
    - Fee-based selection for block building
    """

    DEFAULT_CAPACITY = 10_000
    DEFAULT_TTL_SECS = 3600       # 1 hour
    MIN_GAS_PRICE    = 1

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        ttl_secs: float = DEFAULT_TTL_SECS,
        min_gas_price: int = MIN_GAS_PRICE,
    ):
        self._capacity     = capacity
        self._ttl          = ttl_secs
        self._min_gas      = min_gas_price

        # tx_id → PendingTransaction (for fast lookup / dedup)
        self._txs: Dict[str, PendingTransaction] = {}

        # Max-heap (as min-heap on negated fee): list of PendingTransaction
        self._heap: List[PendingTransaction] = []

        # Per-sender: sorted list of (nonce, tx_id)
        self._by_sender: Dict[str, List[Tuple[int, str]]] = {}

        # Known nonces (sender → set of pending nonces)
        self._nonces: Dict[str, set] = {}

        self.stats = MempoolStats()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add(self, tx: dict, account_nonce: int = 0) -> Tuple[bool, str]:
        """
        Add a transaction to the pool.

        Returns (success, reason).
        """
        tx_id = tx.get("tx_id", "")
        if not tx_id:
            return False, "Missing tx_id"

        # Duplicate check
        if tx_id in self._txs:
            self.stats.duplicates += 1
            return False, "Duplicate transaction"

        # Gas price floor
        gas_price = tx.get("gas_price", 1)
        if gas_price < self._min_gas:
            return False, f"Gas price {gas_price} below minimum {self._min_gas}"

        # Nonce check
        sender = tx.get("from", "")
        nonce  = tx.get("nonce", 0)
        if nonce < account_nonce:
            return False, f"Nonce {nonce} already used (account nonce: {account_nonce})"

        pending_tx = PendingTransaction(
            tx_id     = tx_id,
            from_addr = sender,
            to_addr   = tx.get("to", ""),
            amount    = tx.get("amount", 0),
            gas_price = gas_price,
            gas_limit = tx.get("gas_limit", 21_000),
            nonce     = nonce,
            data      = tx.get("data", b""),
            raw       = tx,
        )

        # Evict if at capacity (remove lowest-fee tx)
        if len(self._txs) >= self._capacity:
            self._evict_lowest_fee()

        # Store
        self._txs[tx_id] = pending_tx
        heapq.heappush(self._heap, pending_tx)

        # Track per-sender nonces
        self._nonces.setdefault(sender, set()).add(nonce)
        nonce_list = self._by_sender.setdefault(sender, [])
        nonce_list.append((nonce, tx_id))
        nonce_list.sort()

        self.stats.total_added += 1
        return True, "OK"

    def select_for_block(self, max_gas: int = 8_000_000, max_txs: int = 500) -> List[dict]:
        """
        Select the best transactions for a new block.

        Ordered by gas_price descending; respects max gas and tx count.
        Also enforces per-sender nonce ordering.
        """
        self._evict_expired()

        selected      = []
        total_gas     = 0
        sender_nonces: Dict[str, int] = {}  # sender → expected nonce
        seen          = set()

        # Work through a sorted copy (by fee descending)
        sorted_txs = sorted(self._txs.values(), reverse=True)  # uses __lt__

        for ptx in sorted_txs:
            if len(selected) >= max_txs:
                break
            if total_gas + ptx.gas_limit > max_gas:
                continue
            if ptx.tx_id in seen:
                continue

            # Nonce ordering: must be consecutive per sender
            expected = sender_nonces.get(ptx.from_addr, ptx.nonce)
            if ptx.nonce < expected:
                continue  # Already processed a higher nonce
            if ptx.nonce > expected:
                self.stats.nonce_gaps += 1
                continue  # Gap — skip until gap is filled

            sender_nonces[ptx.from_addr] = ptx.nonce + 1
            selected.append(ptx.raw)
            total_gas += ptx.gas_limit
            seen.add(ptx.tx_id)

        return selected

    def remove(self, tx_id: str) -> bool:
        """Remove a transaction (e.g., after it is mined)."""
        if tx_id not in self._txs:
            return False
        ptx = self._txs.pop(tx_id)
        # Clean up sender tracking
        nonces = self._nonces.get(ptx.from_addr, set())
        nonces.discard(ptx.nonce)
        sender_list = self._by_sender.get(ptx.from_addr, [])
        self._by_sender[ptx.from_addr] = [
            (n, tid) for n, tid in sender_list if tid != tx_id
        ]
        self.stats.total_mined += 1
        return True

    def remove_batch(self, tx_ids: List[str]):
        for tx_id in tx_ids:
            self.remove(tx_id)

    def get(self, tx_id: str) -> Optional[dict]:
        ptx = self._txs.get(tx_id)
        return ptx.raw if ptx else None

    def contains(self, tx_id: str) -> bool:
        return tx_id in self._txs

    def pending_for(self, address: str) -> List[dict]:
        """All pending transactions from a given sender (nonce order)."""
        nonce_list = self._by_sender.get(address, [])
        return [
            self._txs[tid].raw
            for _, tid in nonce_list
            if tid in self._txs
        ]

    def size(self) -> int:
        return len(self._txs)

    def is_empty(self) -> bool:
        return len(self._txs) == 0

    # ── Eviction ──────────────────────────────────────────────────────────────

    def _evict_lowest_fee(self):
        """Remove the transaction with the lowest gas fee."""
        if not self._txs:
            return
        lowest = min(self._txs.values(), key=lambda t: t.fee())
        self.remove(lowest.tx_id)
        self.stats.total_evicted += 1

    def _evict_expired(self):
        """Remove transactions that have exceeded TTL."""
        cutoff = time.time() - self._ttl
        expired = [
            tx_id for tx_id, ptx in self._txs.items()
            if ptx.timestamp < cutoff
        ]
        for tx_id in expired:
            self._txs.pop(tx_id, None)
            self.stats.total_evicted += 1

    # ── Stats ──────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        self._evict_expired()
        return {
            "size":           self.size(),
            "capacity":       self._capacity,
            "total_added":    self.stats.total_added,
            "total_mined":    self.stats.total_mined,
            "total_evicted":  self.stats.total_evicted,
            "duplicates":     self.stats.duplicates,
            "nonce_gaps":     self.stats.nonce_gaps,
        }
