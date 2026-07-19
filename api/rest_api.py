#!/usr/bin/env python3
"""
REST API — SatoshiOS HTTP Interface

Provides a Flask-based REST API for:
  - Querying blocks and transactions
  - Submitting transactions
  - Reading account balances
  - Node and network status
  - AI security threat status

Run with:  python -m api.rest_api
"""

import time
import hashlib
import json
from typing import Any, Dict, Optional

try:
    from flask import Flask, jsonify, request, abort
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    # Minimal stub for environments without Flask
    class Flask:
        def __init__(self, *a, **kw): pass
        def route(self, *a, **kw):
            def decorator(f): return f
            return decorator
        def run(self, *a, **kw): pass

MIN_GAS_LIMIT = 21_000   # Minimum gas for a plain transfer
# Default storage path.  Prefer the environment variable SATOSHI_CHAIN_PATH;
# fall back to ~/.satoshi_chain which is always writable without root privileges.
import os as _os
DEFAULT_CHAIN_PATH = _os.environ.get(
    "SATOSHI_CHAIN_PATH",
    _os.path.join(_os.path.expanduser("~"), ".satoshi_chain"),
)
del _os

from core.storage.leveldb_store import LevelDBStore
from core.storage.mempool import Mempool
from core.consensus.hybrid_consensus import HybridConsensus, NetworkMetrics


# ─── App Factory ─────────────────────────────────────────────────────────────

def create_app(
    store: Optional[LevelDBStore] = None,
    mempool: Optional[Mempool] = None,
    consensus: Optional[HybridConsensus] = None,
) -> Flask:
    """
    Create and configure the Flask application.

    Dependencies (store, mempool, consensus) can be injected for testing.
    """
    app = Flask(__name__)

    # Defaults
    if store is None:
        store = LevelDBStore(DEFAULT_CHAIN_PATH)
    if mempool is None:
        mempool = Mempool()
    if consensus is None:
        consensus = HybridConsensus()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def ok(data: Any, status: int = 200):
        return jsonify({"success": True, "data": data}), status

    def err(message: str, status: int = 400):
        return jsonify({"success": False, "error": message}), status

    def require_json():
        if not request.is_json:
            abort(415, "Content-Type must be application/json")
        return request.get_json()

    # ── Health ────────────────────────────────────────────────────────────────

    @app.route("/health", methods=["GET"])
    def health():
        return ok({
            "status":    "ok",
            "timestamp": int(time.time()),
            "version":   "1.0.0",
        })

    # ── Blocks ────────────────────────────────────────────────────────────────

    @app.route("/blocks/latest", methods=["GET"])
    def get_latest_block():
        height = store.get_height()
        block  = store.get_block_by_index(height)
        if not block:
            return err("No blocks found", 404)
        return ok(block)

    @app.route("/blocks/<int:index>", methods=["GET"])
    def get_block_by_index(index: int):
        block = store.get_block_by_index(index)
        if not block:
            return err(f"Block #{index} not found", 404)
        return ok(block)

    @app.route("/blocks/hash/<string:block_hash>", methods=["GET"])
    def get_block_by_hash(block_hash: str):
        block = store.get_block_by_hash(block_hash)
        if not block:
            return err(f"Block {block_hash} not found", 404)
        return ok(block)

    @app.route("/blocks", methods=["GET"])
    def list_blocks():
        page  = max(0, int(request.args.get("page", 0)))
        limit = min(100, int(request.args.get("limit", 20)))
        height = store.get_height()

        start = max(0, height - page * limit - limit + 1)
        end   = max(0, height - page * limit)

        blocks = list(store.iter_blocks(start, end))
        blocks.reverse()  # Latest first

        return ok({
            "blocks":      blocks,
            "page":        page,
            "limit":       limit,
            "total_height": height,
        })

    # ── Transactions ──────────────────────────────────────────────────────────

    @app.route("/transactions/<string:tx_id>", methods=["GET"])
    def get_transaction(tx_id: str):
        # Check confirmed
        tx = store.get_transaction(tx_id)
        if tx:
            return ok({**tx, "status": "confirmed"})
        # Check pending
        pending = mempool.get(tx_id)
        if pending:
            return ok({**pending, "status": "pending"})
        return err(f"Transaction {tx_id} not found", 404)

    @app.route("/transactions", methods=["POST"])
    def submit_transaction():
        body = require_json()

        required_fields = ["from", "to", "amount", "nonce"]
        for field in required_fields:
            if field not in body:
                return err(f"Missing field: {field}")

        # Build transaction
        from_addr = body["from"]
        to_addr   = body["to"]
        amount    = int(body["amount"])
        nonce     = int(body["nonce"])
        gas_price = int(body.get("gas_price", 1))
        gas_limit = int(body.get("gas_limit", 21_000))
        data      = body.get("data", "")

        if amount <= 0:
            return err("Amount must be positive")
        if gas_limit < MIN_GAS_LIMIT:
            return err(f"Gas limit too low (minimum {MIN_GAS_LIMIT})")

        # Generate tx_id
        raw = f"{from_addr}{to_addr}{amount}{nonce}{int(time.time())}"
        tx_id = hashlib.sha256(raw.encode()).hexdigest()

        tx = {
            "tx_id":     tx_id,
            "from":      from_addr,
            "to":        to_addr,
            "amount":    amount,
            "nonce":     nonce,
            "gas_price": gas_price,
            "gas_limit": gas_limit,
            "data":      data,
            "timestamp": int(time.time()),
        }

        # Get account nonce from storage
        account_state = store.get_account_state(from_addr)
        account_nonce = account_state.get("nonce", 0)

        success, reason = mempool.add(tx, account_nonce=account_nonce)
        if not success:
            return err(f"Transaction rejected: {reason}")

        return ok({"tx_id": tx_id, "status": "pending"}, 201)

    @app.route("/transactions/pending", methods=["GET"])
    def get_pending_transactions():
        address = request.args.get("address")
        if address:
            txs = mempool.pending_for(address)
        else:
            txs = mempool.select_for_block(max_txs=50)
        return ok({"transactions": txs, "count": len(txs)})

    # ── Accounts ──────────────────────────────────────────────────────────────

    @app.route("/accounts/<string:address>", methods=["GET"])
    def get_account(address: str):
        state = store.get_account_state(address)
        return ok(state)

    @app.route("/accounts/<string:address>/balance", methods=["GET"])
    def get_balance(address: str):
        balance = store.get_balance(address)
        return ok({"address": address, "balance": balance})

    @app.route("/accounts/<string:address>/transactions", methods=["GET"])
    def get_account_transactions(address: str):
        pending = mempool.pending_for(address)
        return ok({
            "address": address,
            "pending": pending,
            "pending_count": len(pending),
        })

    # ── Mempool ───────────────────────────────────────────────────────────────

    @app.route("/mempool", methods=["GET"])
    def get_mempool_stats():
        return ok(mempool.get_stats())

    # ── Network / Node ────────────────────────────────────────────────────────

    @app.route("/node/status", methods=["GET"])
    def node_status():
        stats = store.stats()
        return ok({
            "chain_height":    stats["height"],
            "tip_hash":        stats["tip"],
            "mempool_size":    mempool.size(),
            "consensus_type":  consensus.consensus_type.value if consensus else "unknown",
            "timestamp":       int(time.time()),
            "version":         "1.0.0",
        })

    @app.route("/consensus", methods=["GET"])
    def get_consensus():
        if consensus:
            tip = consensus.get_latest_block()
            return ok({
                "type":         consensus.consensus_type.value,
                "chain_length": consensus.get_chain_length(),
                "tip_hash":     tip.hash if tip else None,
            })
        return ok({"type": "unknown"})

    @app.route("/consensus/metrics", methods=["POST"])
    def update_consensus_metrics():
        body = require_json()
        if consensus:
            metrics = NetworkMetrics(
                online_nodes=body.get("online_nodes", 100),
                total_nodes=body.get("total_nodes", 100),
                avg_latency_ms=body.get("avg_latency_ms", 50),
                transaction_backlog=body.get("transaction_backlog", 0),
                threat_level=body.get("threat_level", 0),
                recent_attacks=body.get("recent_attacks", 0),
            )
            consensus.update_metrics(metrics)
        return ok({"updated": True})

    # ── Storage Stats ─────────────────────────────────────────────────────────

    @app.route("/stats", methods=["GET"])
    def get_stats():
        return ok({
            "chain":   store.stats(),
            "mempool": mempool.get_stats(),
            "timestamp": int(time.time()),
        })

    return app


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not FLASK_AVAILABLE:
        print("[API] Flask not installed. Run: pip install flask")
        exit(1)

    print("[API] Starting SatoshiOS REST API on http://0.0.0.0:8080")
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)
