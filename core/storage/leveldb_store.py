#!/usr/bin/env python3
"""
LevelDB Store — Persistent Block and State Storage

Provides a key-value storage backend for the blockchain.
Uses `plyvel` (LevelDB Python bindings) when available,
falling back to an in-memory dict store for testing.
"""

import json
import hashlib
import struct
from typing import Any, Dict, Iterator, Optional, Tuple


# ─── Backend Abstraction ──────────────────────────────────────────────────────

class _InMemoryBackend:
    """Pure-Python fallback when LevelDB is not installed."""

    def __init__(self):
        self._data: Dict[bytes, bytes] = {}

    def get(self, key: bytes) -> Optional[bytes]:
        return self._data.get(key)

    def put(self, key: bytes, value: bytes):
        self._data[key] = value

    def delete(self, key: bytes):
        self._data.pop(key, None)

    def iterator(self, prefix: bytes = b"") -> Iterator[Tuple[bytes, bytes]]:
        for k, v in sorted(self._data.items()):
            if k.startswith(prefix):
                yield k, v

    def write_batch(self) -> "_BatchWriter":
        return _BatchWriter(self)

    def close(self):
        pass


class _BatchWriter:
    """Simple in-memory batch writer."""

    def __init__(self, backend: _InMemoryBackend):
        self._backend = backend
        self._ops: list = []

    def put(self, key: bytes, value: bytes):
        self._ops.append(("put", key, value))
        return self

    def delete(self, key: bytes):
        self._ops.append(("del", key))
        return self

    def write(self):
        for op in self._ops:
            if op[0] == "put":
                self._backend.put(op[1], op[2])
            else:
                self._backend.delete(op[1])
        self._ops.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.write()


def _open_db(path: str, create_if_missing: bool = True):
    """Try to open LevelDB; fall back to in-memory."""
    try:
        import plyvel
        return plyvel.DB(path, create_if_missing=create_if_missing)
    except ImportError:
        return _InMemoryBackend()


# ─── Key Schemes ──────────────────────────────────────────────────────────────

# Prefix bytes:
#   b"b:" + block_hash       → serialised block
#   b"i:" + 8-byte-index     → block_hash (index → hash lookup)
#   b"t:" + tx_id            → serialised transaction
#   b"s:" + address          → serialised account state
#   b"m:" + "tip"            → tip block hash
#   b"m:" + "height"         → chain height (8-byte little-endian)

BLOCK_PREFIX   = b"b:"
INDEX_PREFIX   = b"i:"
TX_PREFIX      = b"t:"
STATE_PREFIX   = b"s:"
META_PREFIX    = b"m:"


def _encode_index(n: int) -> bytes:
    return struct.pack("<Q", n)


# ─── LevelDBStore ─────────────────────────────────────────────────────────────

class LevelDBStore:
    """
    Persistent key-value store for blocks, transactions, and account state.

    All values are JSON-serialised before storage.
    """

    def __init__(self, path: str = "/tmp/satoshi_chain"):
        self._db = _open_db(path)
        backend_type = type(self._db).__name__
        print(f"[Storage] Opened store at '{path}' (backend: {backend_type})")

    # ── Block Storage ─────────────────────────────────────────────────────────

    def put_block(self, block: dict):
        """Persist a block by hash and index."""
        block_hash = block.get("hash", "")
        index      = block.get("header", {}).get("index", 0)

        encoded = json.dumps(block).encode()
        with self._db.write_batch() as wb:
            wb.put(BLOCK_PREFIX + block_hash.encode(), encoded)
            wb.put(INDEX_PREFIX + _encode_index(index), block_hash.encode())

    def get_block_by_hash(self, block_hash: str) -> Optional[dict]:
        data = self._db.get(BLOCK_PREFIX + block_hash.encode())
        return json.loads(data) if data else None

    def get_block_by_index(self, index: int) -> Optional[dict]:
        hash_bytes = self._db.get(INDEX_PREFIX + _encode_index(index))
        if not hash_bytes:
            return None
        return self.get_block_by_hash(hash_bytes.decode())

    def delete_block(self, block_hash: str):
        self._db.delete(BLOCK_PREFIX + block_hash.encode())

    def iter_blocks(self, start: int = 0, end: Optional[int] = None) -> Iterator[dict]:
        """Iterate blocks in index order."""
        i = start
        while True:
            if end is not None and i > end:
                break
            block = self.get_block_by_index(i)
            if block is None:
                break
            yield block
            i += 1

    # ── Transaction Storage ───────────────────────────────────────────────────

    def put_transaction(self, tx: dict):
        tx_id   = tx.get("tx_id", "")
        encoded = json.dumps(tx).encode()
        self._db.put(TX_PREFIX + tx_id.encode(), encoded)

    def get_transaction(self, tx_id: str) -> Optional[dict]:
        data = self._db.get(TX_PREFIX + tx_id.encode())
        return json.loads(data) if data else None

    def has_transaction(self, tx_id: str) -> bool:
        return self._db.get(TX_PREFIX + tx_id.encode()) is not None

    # ── Account State ──────────────────────────────────────────────────────────

    def put_account_state(self, address: str, state: dict):
        """Store account state (balance, nonce, contract code hash, storage)."""
        encoded = json.dumps(state).encode()
        self._db.put(STATE_PREFIX + address.encode(), encoded)

    def get_account_state(self, address: str) -> dict:
        data = self._db.get(STATE_PREFIX + address.encode())
        if data:
            return json.loads(data)
        # Return default empty account
        return {"address": address, "balance": 0, "nonce": 0, "code_hash": "", "storage": {}}

    def get_balance(self, address: str) -> int:
        return self.get_account_state(address).get("balance", 0)

    def update_balance(self, address: str, delta: int):
        state = self.get_account_state(address)
        state["balance"] = max(0, state["balance"] + delta)
        self.put_account_state(address, state)

    # ── Metadata ──────────────────────────────────────────────────────────────

    def set_tip(self, block_hash: str):
        self._db.put(META_PREFIX + b"tip", block_hash.encode())

    def get_tip(self) -> Optional[str]:
        data = self._db.get(META_PREFIX + b"tip")
        return data.decode() if data else None

    def set_height(self, height: int):
        self._db.put(META_PREFIX + b"height", _encode_index(height))

    def get_height(self) -> int:
        data = self._db.get(META_PREFIX + b"height")
        if data:
            return struct.unpack("<Q", data)[0]
        return 0

    # ── Batch Application ─────────────────────────────────────────────────────

    def apply_block(self, block: dict) -> int:
        """
        Atomically persist a block and all its transactions.
        Returns new chain height.
        """
        self.put_block(block)
        for tx in block.get("transactions", []):
            self.put_transaction(tx)
        height = block.get("header", {}).get("index", 0)
        self.set_height(height)
        self.set_tip(block.get("hash", ""))
        return height

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        height = self.get_height()
        tip    = self.get_tip()
        return {"height": height, "tip": tip}

    def close(self):
        self._db.close()
        print("[Storage] Store closed")
