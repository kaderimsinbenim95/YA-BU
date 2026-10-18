#!/usr/bin/env python3
"""
Gas Meter — Transaction Cost Accounting

Defines the gas cost table for every opcode and provides a GasMeter
that tracks consumption and enforces the gas limit.
"""

from enum import IntEnum
from typing import Dict


# ─── Opcodes ──────────────────────────────────────────────────────────────────

class Opcode(IntEnum):
    """SatoshiVM bytecode opcodes."""
    # Stack
    PUSH   = 0x01   # PUSH <value>
    POP    = 0x02
    DUP    = 0x03
    SWAP   = 0x04

    # Arithmetic
    ADD    = 0x10
    SUB    = 0x11
    MUL    = 0x12
    DIV    = 0x13
    MOD    = 0x14
    EXP    = 0x15

    # Comparison
    EQ     = 0x20
    NEQ    = 0x21
    LT     = 0x22
    GT     = 0x23
    LE     = 0x24
    GE     = 0x25

    # Logic
    AND    = 0x30
    OR     = 0x31
    NOT    = 0x32

    # Memory
    MLOAD  = 0x40   # MLOAD <addr>  — load word from memory
    MSTORE = 0x41   # MSTORE <addr> — store word to memory

    # Storage (persistent, costs more)
    SLOAD  = 0x50   # SLOAD <key>
    SSTORE = 0x51   # SSTORE <key> <value>

    # Control flow
    JUMP   = 0x60   # JUMP <offset>
    JUMPI  = 0x61   # JUMPI <offset> <condition>
    HALT   = 0x62
    REVERT = 0x63

    # Environment
    CALLER    = 0x70
    CALLVALUE = 0x71
    ADDRESS   = 0x72
    BALANCE   = 0x73
    BLOCKHASH = 0x74
    TIMESTAMP = 0x75

    # Calls
    CALL       = 0x80   # CALL <address> <value> <gas>
    STATICCALL = 0x81
    RETURN     = 0x82

    # Hashing
    SHA256 = 0x90

    # Logging
    LOG  = 0xA0   # LOG <topic> <data>
    LOG2 = 0xA1


# ─── Gas Table ────────────────────────────────────────────────────────────────

GAS_TABLE: Dict[int, int] = {
    Opcode.PUSH:      3,
    Opcode.POP:       2,
    Opcode.DUP:       3,
    Opcode.SWAP:      3,

    Opcode.ADD:       3,
    Opcode.SUB:       3,
    Opcode.MUL:       5,
    Opcode.DIV:       5,
    Opcode.MOD:       5,
    Opcode.EXP:      50,

    Opcode.EQ:        3,
    Opcode.NEQ:       3,
    Opcode.LT:        3,
    Opcode.GT:        3,
    Opcode.LE:        3,
    Opcode.GE:        3,

    Opcode.AND:       3,
    Opcode.OR:        3,
    Opcode.NOT:       3,

    Opcode.MLOAD:    200,
    Opcode.MSTORE:   200,

    Opcode.SLOAD:   2100,   # Cold storage read (EIP-2929 style)
    Opcode.SSTORE:  20000,  # Storage write

    Opcode.JUMP:      8,
    Opcode.JUMPI:    10,
    Opcode.HALT:      0,
    Opcode.REVERT:    0,

    Opcode.CALLER:    2,
    Opcode.CALLVALUE: 2,
    Opcode.ADDRESS:   2,
    Opcode.BALANCE:  400,
    Opcode.BLOCKHASH: 20,
    Opcode.TIMESTAMP: 2,

    Opcode.CALL:    2600,
    Opcode.STATICCALL: 100,
    Opcode.RETURN:    0,

    Opcode.SHA256:   30,    # + 6 per word
    Opcode.LOG:      375,
    Opcode.LOG2:     750,
}

# Minimum gas for a plain value transfer (no contract execution)
TX_BASE_GAS      = 21_000
# Gas per non-zero byte of calldata
CALLDATA_NONZERO = 16
# Gas per zero byte of calldata
CALLDATA_ZERO    = 4
# Gas stipend given to called contracts
CALL_STIPEND     = 2_300


# ─── GasMeter ─────────────────────────────────────────────────────────────────

class OutOfGasError(Exception):
    """Raised when gas is exhausted during execution."""
    pass


class GasMeter:
    """
    Tracks gas usage during contract execution.

    * Charged per opcode via `charge(opcode)`
    * Extra dynamic gas (e.g., calldata length) via `charge_raw(amount)`
    * Refunds (e.g., SSTORE clearing) via `refund(amount)`
    * Final cost: `used() - min(refund, used() // 5)`
    """

    def __init__(self, gas_limit: int):
        if gas_limit <= 0:
            raise ValueError(f"Gas limit must be positive, got {gas_limit}")
        self._limit:    int = gas_limit
        self._used:     int = 0
        self._refunds:  int = 0

    # ── Charging ──────────────────────────────────────────────────────────────

    def charge(self, opcode: int):
        """Charge gas for a single opcode."""
        cost = GAS_TABLE.get(opcode, 3)
        self._consume(cost)

    def charge_raw(self, amount: int):
        """Charge an arbitrary gas amount (e.g., dynamic calldata cost)."""
        if amount < 0:
            raise ValueError("Gas charge cannot be negative")
        self._consume(amount)

    def charge_calldata(self, data: bytes):
        """Charge for calldata bytes (non-zero = 16, zero = 4)."""
        cost = sum(CALLDATA_NONZERO if b != 0 else CALLDATA_ZERO for b in data)
        self._consume(cost)

    def refund(self, amount: int):
        """Add a gas refund (e.g., from clearing storage)."""
        self._refunds += max(0, amount)

    # ── Queries ───────────────────────────────────────────────────────────────

    def remaining(self) -> int:
        """Gas units still available."""
        return self._limit - self._used

    def used(self) -> int:
        """Raw gas consumed (before refunds)."""
        return self._used

    def effective_used(self) -> int:
        """Gas consumed after applying refund (capped at used // 5)."""
        max_refund = self._used // 5
        actual_refund = min(self._refunds, max_refund)
        return self._used - actual_refund

    def limit(self) -> int:
        return self._limit

    def is_exhausted(self) -> bool:
        return self._used >= self._limit

    # ── Snapshot / Restore (for sub-calls) ───────────────────────────────────

    def snapshot(self) -> dict:
        return {"used": self._used, "refunds": self._refunds}

    def restore(self, snap: dict):
        self._used    = snap["used"]
        self._refunds = snap["refunds"]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _consume(self, amount: int):
        if self._used + amount > self._limit:
            raise OutOfGasError(
                f"Out of gas: tried to use {self._used + amount}, limit {self._limit}"
            )
        self._used += amount

    def __repr__(self) -> str:
        return (
            f"GasMeter(limit={self._limit}, used={self._used}, "
            f"remaining={self.remaining()}, refunds={self._refunds})"
        )
