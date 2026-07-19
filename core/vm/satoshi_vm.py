#!/usr/bin/env python3
"""
SatoshiVM — Stack-Based Virtual Machine

Executes SatoshiVM bytecode produced by the BytecodeCompiler.
Supports arithmetic, logic, memory, storage, control flow, and
environment queries.  Gas is metered via GasMeter.

Control-flow convention — JUMPI semantics
-----------------------------------------
SatoshiVM's JUMPI instruction jumps when the condition is **FALSY** (zero,
None, or False).  This is the opposite of EVM (which jumps when the condition
is truthy) and is sometimes called a "JUMPZ" (jump-if-zero) in other VMs.

Rationale: the bytecode compiler emits JUMPI to skip over a branch body when
the guard condition fails.  For ``if cond { body }``, the compiler evaluates
*cond*, emits ``JUMPI → end_label``, then emits *body*, then places
``end_label``.  This matches the natural structure of if-else trees and
requires no additional NOT at the call site.

Developers porting code from EVM should invert their condition before emitting
JUMPI, or use ``NOT`` + ``JUMPI``.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from core.vm.gas_meter import GasMeter, OutOfGasError, Opcode
from core.vm.bytecode_compiler import Bytecode, Instruction


# ─── Execution Context ────────────────────────────────────────────────────────

class ExecutionContext:
    """
    Represents the environment visible to a running contract.

    Passed in at call-time; the VM reads from it for ENV opcodes.
    """

    def __init__(
        self,
        caller:     str = "0x0",
        address:    str = "0x0",
        call_value: int = 0,
        block_hash: str = "0" * 64,
        timestamp:  int = 0,
        block_number: int = 0,
        storage:    Optional[Dict[str, Any]] = None,
    ):
        self.caller       = caller
        self.address      = address
        self.call_value   = call_value
        self.block_hash   = block_hash
        self.timestamp    = timestamp or int(time.time())
        self.block_number = block_number
        self.storage: Dict[str, Any] = storage if storage is not None else {}
        # Uncommitted storage writes (committed on HALT)
        self.pending_storage: Dict[str, Any] = {}


# ─── VM Result ────────────────────────────────────────────────────────────────

class VMResult:
    def __init__(
        self,
        success:      bool,
        return_value: Any,
        gas_used:     int,
        gas_limit:    int,
        logs:         List[dict],
        error:        Optional[str] = None,
        storage_diff: Optional[Dict[str, Any]] = None,
    ):
        self.success      = success
        self.return_value = return_value
        self.gas_used     = gas_used
        self.gas_limit    = gas_limit
        self.logs         = logs
        self.error        = error
        self.storage_diff = storage_diff or {}

    def __repr__(self) -> str:
        status = "✅ OK" if self.success else f"❌ FAIL: {self.error}"
        return (
            f"VMResult({status}, gas={self.gas_used}/{self.gas_limit}, "
            f"return={self.return_value}, logs={len(self.logs)})"
        )


# ─── SatoshiVM ────────────────────────────────────────────────────────────────

MAX_STACK_DEPTH  = 1024
MAX_CALL_DEPTH   = 128
MAX_MEMORY_WORDS = 65_536    # 64K words


class SatoshiVM:
    """
    Stack-based virtual machine for SatoshiLang smart contracts.

    Execution model:
    - Operand stack (LIFO)
    - Linear word-addressed memory (volatile)
    - Key-value storage (persistent via ExecutionContext)
    - Program counter (PC)
    - Gas meter
    """

    def __init__(self):
        self._stack:   List[Any]       = []
        self._memory:  Dict[int, Any]  = {}
        self._pc:      int             = 0
        self._logs:    List[dict]      = []
        self._call_depth: int          = 0

    # ── Public Entry Points ───────────────────────────────────────────────────

    def execute(
        self,
        bytecode:  Bytecode,
        ctx:       ExecutionContext,
        gas_limit: int = 1_000_000,
    ) -> VMResult:
        """Execute a bytecode program and return the result."""
        self._reset()
        meter = GasMeter(gas_limit)

        try:
            return_value = self._run(bytecode, ctx, meter)
            # Commit pending storage on success
            ctx.storage.update(ctx.pending_storage)
            return VMResult(
                success      = True,
                return_value = return_value,
                gas_used     = meter.effective_used(),
                gas_limit    = gas_limit,
                logs         = self._logs,
                storage_diff = dict(ctx.pending_storage),
            )
        except OutOfGasError as e:
            return VMResult(
                success=False, return_value=None,
                gas_used=gas_limit, gas_limit=gas_limit,
                logs=[], error=f"OutOfGas: {e}",
            )
        except VMError as e:
            return VMResult(
                success=False, return_value=None,
                gas_used=meter.used(), gas_limit=gas_limit,
                logs=[], error=str(e),
            )
        except Exception as e:
            return VMResult(
                success=False, return_value=None,
                gas_used=meter.used(), gas_limit=gas_limit,
                logs=[], error=f"InternalError: {e}",
            )

    def call_function(
        self,
        bytecode:  Bytecode,
        fn_offset: int,
        args:      List[Any],
        ctx:       ExecutionContext,
        gas_limit: int = 500_000,
    ) -> VMResult:
        """Call a specific function by its bytecode offset."""
        if self._call_depth >= MAX_CALL_DEPTH:
            return VMResult(False, None, 0, gas_limit, [], "CallDepthExceeded")

        self._reset()
        self._pc = fn_offset
        # Push args onto the stack
        for arg in reversed(args):
            self._push(arg)

        return self.execute(bytecode, ctx, gas_limit)

    # ── Core Execution Loop ───────────────────────────────────────────────────

    def _run(self, bytecode: Bytecode, ctx: ExecutionContext, meter: GasMeter) -> Any:
        return_value: Any = None

        while self._pc < len(bytecode):
            instr = bytecode[self._pc]
            self._pc += 1

            op = instr.opcode
            meter.charge(op)

            # ── Stack Operations ─────────────────────────────────────────────
            if op == Opcode.PUSH:
                self._push(instr.operands[0] if instr.operands else 0)

            elif op == Opcode.POP:
                self._pop()

            elif op == Opcode.DUP:
                val = self._peek()
                self._push(val)

            elif op == Opcode.SWAP:
                a = self._pop()
                b = self._pop()
                self._push(a)
                self._push(b)

            # ── Arithmetic ────────────────────────────────────────────────────
            elif op == Opcode.ADD:
                b, a = self._pop(), self._pop()
                self._push(self._to_num(a) + self._to_num(b))

            elif op == Opcode.SUB:
                b, a = self._pop(), self._pop()
                self._push(self._to_num(a) - self._to_num(b))

            elif op == Opcode.MUL:
                b, a = self._pop(), self._pop()
                self._push(self._to_num(a) * self._to_num(b))

            elif op == Opcode.DIV:
                b, a = self._pop(), self._pop()
                bv = self._to_num(b)
                self._push(0 if bv == 0 else self._to_num(a) // bv)

            elif op == Opcode.MOD:
                b, a = self._pop(), self._pop()
                bv = self._to_num(b)
                self._push(0 if bv == 0 else self._to_num(a) % bv)

            elif op == Opcode.EXP:
                exp, base = self._pop(), self._pop()
                self._push(pow(int(self._to_num(base)), max(0, int(self._to_num(exp)))))

            # ── Comparison ────────────────────────────────────────────────────
            elif op == Opcode.EQ:
                b, a = self._pop(), self._pop()
                self._push(1 if a == b else 0)

            elif op == Opcode.NEQ:
                b, a = self._pop(), self._pop()
                self._push(1 if a != b else 0)

            elif op == Opcode.LT:
                b, a = self._pop(), self._pop()
                self._push(1 if self._to_num(a) < self._to_num(b) else 0)

            elif op == Opcode.GT:
                b, a = self._pop(), self._pop()
                self._push(1 if self._to_num(a) > self._to_num(b) else 0)

            elif op == Opcode.LE:
                b, a = self._pop(), self._pop()
                self._push(1 if self._to_num(a) <= self._to_num(b) else 0)

            elif op == Opcode.GE:
                b, a = self._pop(), self._pop()
                self._push(1 if self._to_num(a) >= self._to_num(b) else 0)

            # ── Logic ─────────────────────────────────────────────────────────
            elif op == Opcode.AND:
                b, a = self._pop(), self._pop()
                self._push(1 if a and b else 0)

            elif op == Opcode.OR:
                b, a = self._pop(), self._pop()
                self._push(1 if a or b else 0)

            elif op == Opcode.NOT:
                a = self._pop()
                self._push(0 if a else 1)

            # ── Memory ────────────────────────────────────────────────────────
            elif op == Opcode.MLOAD:
                addr = instr.operands[0] if instr.operands else self._pop()
                self._push(self._memory.get(int(addr), 0))

            elif op == Opcode.MSTORE:
                addr = instr.operands[0] if instr.operands else self._pop()
                val  = self._pop()
                if len(self._memory) >= MAX_MEMORY_WORDS:
                    raise VMError("Memory limit exceeded")
                self._memory[int(addr)] = val

            # ── Storage ───────────────────────────────────────────────────────
            elif op == Opcode.SLOAD:
                key = str(self._pop())
                val = ctx.pending_storage.get(key, ctx.storage.get(key, 0))
                self._push(val)

            elif op == Opcode.SSTORE:
                val = self._pop()
                key = str(self._pop())
                # Gas refund if clearing a slot
                if key in ctx.storage and val == 0:
                    meter.refund(15_000)
                ctx.pending_storage[key] = val

            # ── Control Flow ──────────────────────────────────────────────────
            elif op == Opcode.JUMP:
                offset = instr.operands[0] if instr.operands else self._pop()
                if offset is None:
                    raise VMError("JUMP target unresolved")
                self._pc = int(offset)

            elif op == Opcode.JUMPI:
                offset    = instr.operands[0] if instr.operands else self._pop()
                condition = self._pop()
                # JUMPI in SatoshiVM jumps when condition is FALSY (zero/None/False).
                # This matches the bytecode compiler which emits JUMPI for "if false → else"
                # and "while false → end" branches.
                if not condition:
                    if offset is None:
                        raise VMError("JUMPI target unresolved")
                    self._pc = int(offset)

            elif op == Opcode.HALT:
                break

            elif op == Opcode.REVERT:
                msg = str(self._pop()) if self._stack else "reverted"
                raise VMError(f"REVERT: {msg}")

            # ── Environment ───────────────────────────────────────────────────
            elif op == Opcode.CALLER:
                self._push(ctx.caller)

            elif op == Opcode.CALLVALUE:
                self._push(ctx.call_value)

            elif op == Opcode.ADDRESS:
                self._push(ctx.address)

            elif op == Opcode.BALANCE:
                addr = str(self._pop())
                bal  = ctx.storage.get(f"__balance_{addr}", 0)
                self._push(bal)

            elif op == Opcode.BLOCKHASH:
                self._push(ctx.block_hash)

            elif op == Opcode.TIMESTAMP:
                self._push(ctx.timestamp)

            # ── Calls ─────────────────────────────────────────────────────────
            elif op == Opcode.CALL:
                # Simplified: resolve as a no-op (real cross-contract calls
                # require a full world state reference)
                offset = instr.operands[0] if instr.operands else None
                if offset is not None and isinstance(offset, int) and offset < len(bytecode):
                    # Internal function call — jump to offset, push return address
                    self._memory[-self._call_depth - 1] = self._pc
                    self._call_depth += 1
                    self._pc = offset
                else:
                    self._push(0)  # External call — return 0 (success placeholder)

            elif op == Opcode.STATICCALL:
                self._push(0)

            elif op == Opcode.RETURN:
                if self._call_depth > 0:
                    # Return from internal call
                    self._call_depth -= 1
                    ret_addr = self._memory.get(-self._call_depth - 1, len(bytecode))
                    self._pc = ret_addr
                else:
                    return_value = self._pop() if self._stack else None
                    break

            # ── Hashing ───────────────────────────────────────────────────────
            elif op == Opcode.SHA256:
                data = str(self._pop()).encode()
                digest = hashlib.sha256(data).hexdigest()
                # Charge extra per 32-byte word
                words = (len(data) + 31) // 32
                meter.charge_raw(6 * words)
                self._push(digest)

            # ── Logging ───────────────────────────────────────────────────────
            elif op == Opcode.LOG:
                data  = self._pop() if self._stack else None
                topic = self._pop() if self._stack else None
                self._logs.append({
                    "address": ctx.address,
                    "topic":   topic,
                    "data":    data,
                    "timestamp": ctx.timestamp,
                })

            elif op == Opcode.LOG2:
                data   = self._pop() if self._stack else None
                topic2 = self._pop() if self._stack else None
                topic1 = self._pop() if self._stack else None
                self._logs.append({
                    "address": ctx.address,
                    "topics":  [topic1, topic2],
                    "data":    data,
                })

            else:
                raise VMError(f"Unknown opcode: 0x{op:02x}")

        # Top of stack is the implicit return value
        if return_value is None and self._stack:
            return_value = self._stack[-1]

        return return_value

    # ── Stack Helpers ─────────────────────────────────────────────────────────

    def _push(self, value: Any):
        if len(self._stack) >= MAX_STACK_DEPTH:
            raise VMError("Stack overflow")
        self._stack.append(value)

    def _pop(self) -> Any:
        if not self._stack:
            raise VMError("Stack underflow")
        return self._stack.pop()

    def _peek(self) -> Any:
        if not self._stack:
            raise VMError("Stack underflow (peek)")
        return self._stack[-1]

    @staticmethod
    def _to_num(val: Any) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    def _reset(self):
        self._stack.clear()
        self._memory.clear()
        self._pc          = 0
        self._logs        = []
        self._call_depth  = 0


class VMError(Exception):
    pass
