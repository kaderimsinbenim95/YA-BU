#!/usr/bin/env python3
"""
Bytecode Compiler — SatoshiLang AST → SatoshiVM Bytecode

Walks the AST produced by satoshi_lang.py and emits a flat list of
(opcode, *operands) instructions that the SatoshiVM can execute.
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib

from core.vm.gas_meter import Opcode


# ─── Instruction ─────────────────────────────────────────────────────────────

@dataclass
class Instruction:
    opcode:   int
    operands: List[Any] = field(default_factory=list)
    comment:  str = ""

    def __repr__(self) -> str:
        name = Opcode(self.opcode).name if self.opcode in Opcode._value2member_map_ else f"0x{self.opcode:02x}"
        ops  = " ".join(str(o) for o in self.operands)
        return f"{name} {ops}".strip() + (f"  ; {self.comment}" if self.comment else "")


Bytecode = List[Instruction]


# ─── Symbol Table ─────────────────────────────────────────────────────────────

@dataclass
class Symbol:
    name:   str
    kind:   str   # "local", "param", "global", "function"
    index:  int   # memory slot or function table index


class SymbolTable:
    def __init__(self, parent: Optional["SymbolTable"] = None):
        self._symbols: Dict[str, Symbol] = {}
        self._parent = parent
        self._next_slot = 0

    def define(self, name: str, kind: str = "local") -> Symbol:
        sym = Symbol(name=name, kind=kind, index=self._next_slot)
        self._symbols[name] = sym
        self._next_slot += 1
        return sym

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self._symbols:
            return self._symbols[name]
        if self._parent:
            return self._parent.lookup(name)
        return None

    def child(self) -> "SymbolTable":
        return SymbolTable(parent=self)


# ─── Label / Jump Patching ────────────────────────────────────────────────────

class LabelManager:
    """Manages symbolic jump labels and back-patching."""

    def __init__(self):
        self._labels:     Dict[str, int]          = {}  # label → bytecode offset
        self._backpatch:  List[Tuple[int, str]]   = []  # (instr_index, label)
        self._counter = 0

    def new_label(self, hint: str = "") -> str:
        self._counter += 1
        return f"__L{self._counter}_{hint}"

    def define(self, label: str, offset: int):
        self._labels[label] = offset

    def mark_jump(self, instr_index: int, label: str):
        self._backpatch.append((instr_index, label))

    def patch(self, bytecode: Bytecode):
        """Replace symbolic label operands with resolved offsets."""
        for instr_index, label in self._backpatch:
            offset = self._labels.get(label)
            if offset is None:
                raise CompileError(f"Undefined label: {label}")
            bytecode[instr_index].operands[0] = offset


# ─── Compiler ─────────────────────────────────────────────────────────────────

class CompileError(Exception):
    pass


class BytecodeCompiler:
    """
    Compiles a SatoshiLang AST into SatoshiVM bytecode.

    Entry point:  compiler.compile(ast)  → Bytecode
    """

    def __init__(self):
        self._code:     Bytecode     = []
        self._globals:  SymbolTable  = SymbolTable()
        self._scope:    SymbolTable  = self._globals
        self._labels:   LabelManager = LabelManager()
        self._functions: Dict[str, int] = {}  # name → bytecode entry offset

    def compile(self, ast: Dict[str, Any]) -> Bytecode:
        """Compile a full program AST."""
        self._code.clear()
        self._globals  = SymbolTable()
        self._scope    = self._globals
        self._labels   = LabelManager()
        self._functions.clear()

        if ast.get("type") != "program":
            raise CompileError("Expected program AST node")

        # First pass: register function signatures
        for item in ast.get("items", []):
            if item["type"] == "function":
                self._functions[item["name"]] = -1  # offset TBD

        # Second pass: emit code
        for item in ast.get("items", []):
            self._compile_item(item)

        # Patch jumps
        self._labels.patch(self._code)
        return self._code

    # ── Top-Level Items ───────────────────────────────────────────────────────

    def _compile_item(self, item: Dict[str, Any]):
        t = item.get("type")
        if t == "function":
            self._compile_function(item)
        elif t == "contract":
            self._compile_contract(item)
        else:
            raise CompileError(f"Unknown top-level item type: {t}")

    def _compile_function(self, func: Dict[str, Any]):
        name = func["name"]
        entry_label = f"__fn_{name}"
        self._labels.define(entry_label, len(self._code))
        self._functions[name] = len(self._code)

        # New scope for this function
        prev_scope = self._scope
        self._scope = self._scope.child()

        # Register parameters as symbols
        for param in func.get("params", []):
            self._scope.define(param["name"], kind="param")

        # Compile body statements
        for stmt in func.get("body", []):
            self._compile_stmt(stmt)

        # Implicit halt if no explicit return
        self._emit(Opcode.HALT, comment=f"end of {name}")
        self._scope = prev_scope

    def _compile_contract(self, contract: Dict[str, Any]):
        name = contract["name"]
        self._labels.define(f"__contract_{name}", len(self._code))

        prev_scope = self._scope
        self._scope = self._scope.child()

        for stmt in contract.get("body", []):
            self._compile_stmt(stmt)

        self._emit(Opcode.HALT, comment=f"end of contract {name}")
        self._scope = prev_scope

    # ── Statements ────────────────────────────────────────────────────────────

    def _compile_stmt(self, stmt: Dict[str, Any]):
        t = stmt.get("type")
        if t == "let":
            self._compile_let(stmt)
        elif t == "return":
            self._compile_return(stmt)
        elif t == "if":
            self._compile_if(stmt)
        elif t == "while":
            self._compile_while(stmt)
        elif t in ("call", "identifier", "integer", "string", "binary", "unary"):
            self._compile_expr(stmt)
            self._emit(Opcode.POP, comment="discard expression result")
        else:
            # Best-effort: try as expression
            try:
                self._compile_expr(stmt)
                self._emit(Opcode.POP)
            except CompileError:
                pass  # Unsupported statement — skip

    def _compile_let(self, stmt: Dict[str, Any]):
        name = stmt["name"]
        sym  = self._scope.define(name, kind="local")
        self._compile_expr(stmt["value"])
        self._emit(Opcode.MSTORE, sym.index, comment=f"let {name}")

    def _compile_return(self, stmt: Dict[str, Any]):
        if stmt.get("value"):
            self._compile_expr(stmt["value"])
        self._emit(Opcode.RETURN, comment="return")

    def _compile_if(self, stmt: Dict[str, Any]):
        self._compile_expr(stmt["condition"])

        else_label = self._labels.new_label("else")
        end_label  = self._labels.new_label("endif")

        # JUMPI to else if condition is false
        jump_idx = len(self._code)
        self._emit(Opcode.JUMPI, None, comment="if false → else")  # operand patched
        self._labels.mark_jump(jump_idx, else_label)

        # Then branch
        for s in stmt.get("then", []):
            self._compile_stmt(s)

        if stmt.get("else"):
            # Jump over else
            jump_idx2 = len(self._code)
            self._emit(Opcode.JUMP, None, comment="skip else")
            self._labels.mark_jump(jump_idx2, end_label)

        self._labels.define(else_label, len(self._code))

        if stmt.get("else"):
            for s in stmt["else"]:
                self._compile_stmt(s)

        self._labels.define(end_label, len(self._code))

    def _compile_while(self, stmt: Dict[str, Any]):
        loop_label  = self._labels.new_label("while_cond")
        end_label   = self._labels.new_label("while_end")

        self._labels.define(loop_label, len(self._code))
        self._compile_expr(stmt["condition"])

        jump_idx = len(self._code)
        self._emit(Opcode.JUMPI, None, comment="while false → end")
        self._labels.mark_jump(jump_idx, end_label)

        for s in stmt.get("body", []):
            self._compile_stmt(s)

        back_idx = len(self._code)
        self._emit(Opcode.JUMP, None, comment="back to while cond")
        self._labels.mark_jump(back_idx, loop_label)

        self._labels.define(end_label, len(self._code))

    # ── Expressions ───────────────────────────────────────────────────────────

    def _compile_expr(self, expr: Dict[str, Any]):
        t = expr.get("type")

        if t == "integer":
            self._emit(Opcode.PUSH, expr["value"], comment=f"push {expr['value']}")

        elif t == "float":
            # Store as integer × 1e6 fixed-point
            fixed = int(float(expr["value"]) * 1_000_000)
            self._emit(Opcode.PUSH, fixed, comment=f"push float {expr['value']} as fixed")

        elif t == "string":
            # String literals are mapped to 64-bit integers for VM stack storage
            # by truncating the SHA-256 hash to its first 16 hex characters (64 bits).
            #
            # Trade-offs and limitations:
            #   • Birthday collision boundary: ~2^32 unique strings can be hashed
            #     before a ~50 % collision probability is reached.
            #   • This is acceptable for compile-time string constants in smart
            #     contracts (e.g. event names, permission keys) where the total
            #     number of distinct literals is typically small (< 1 000).
            #   • It is NOT suitable as a cryptographic commitment or where two
            #     different strings must be guaranteed to produce different values.
            #     For that use-case, callers should hash at runtime using the KECCAK
            #     or SHA256 opcodes inside the VM rather than at compile time.
            hval = int(hashlib.sha256(expr["value"].encode()).hexdigest()[:16], 16)
            self._emit(Opcode.PUSH, hval, comment=f'push str "{expr["value"]}"')

        elif t in ("true", "boolean") and expr.get("value") is True:
            self._emit(Opcode.PUSH, 1, comment="push true")

        elif t in ("false", "boolean") and expr.get("value") is False:
            self._emit(Opcode.PUSH, 0, comment="push false")

        elif t == "identifier":
            sym = self._scope.lookup(expr["name"])
            if sym:
                self._emit(Opcode.MLOAD, sym.index, comment=f"load {expr['name']}")
            else:
                # Could be environment variable
                env_opcodes = {
                    "caller":     Opcode.CALLER,
                    "callvalue":  Opcode.CALLVALUE,
                    "address":    Opcode.ADDRESS,
                    "blockhash":  Opcode.BLOCKHASH,
                    "timestamp":  Opcode.TIMESTAMP,
                }
                op = env_opcodes.get(expr["name"].lower())
                if op:
                    self._emit(op)
                else:
                    # Push 0 for unknown identifiers
                    self._emit(Opcode.PUSH, 0, comment=f"unknown id {expr['name']}")

        elif t == "binary":
            self._compile_binary(expr)

        elif t == "unary":
            self._compile_unary(expr)

        elif t == "call":
            self._compile_call(expr)

        elif t == "index":
            self._compile_expr(expr["object"])
            self._compile_expr(expr["index"])
            self._emit(Opcode.ADD)   # Simplified: base + index offset
            self._emit(Opcode.MLOAD)

        else:
            # Unknown expression — push 0
            self._emit(Opcode.PUSH, 0, comment=f"unknown expr type {t}")

    def _compile_binary(self, expr: Dict[str, Any]):
        op = expr.get("op", "")

        # Short-circuit evaluation for logical ops
        if op == "&&":
            self._compile_expr(expr["left"])
            self._emit(Opcode.DUP)
            skip_label = self._labels.new_label("and_skip")
            jmp_idx = len(self._code)
            self._emit(Opcode.JUMPI, None, comment="short-circuit &&")
            self._labels.mark_jump(jmp_idx, skip_label)
            self._emit(Opcode.POP)
            self._compile_expr(expr["right"])
            self._labels.define(skip_label, len(self._code))
            return

        if op == "||":
            self._compile_expr(expr["left"])
            self._emit(Opcode.DUP)
            do_label = self._labels.new_label("or_done")
            jmp_idx  = len(self._code)
            self._emit(Opcode.JUMPI, None, comment="short-circuit ||")
            self._labels.mark_jump(jmp_idx, do_label)
            self._emit(Opcode.POP)
            self._compile_expr(expr["right"])
            self._labels.define(do_label, len(self._code))
            return

        # For all other binary ops, evaluate both sides first
        self._compile_expr(expr["left"])
        self._compile_expr(expr["right"])

        opcode_map = {
            "+":  Opcode.ADD,  "-":  Opcode.SUB,
            "*":  Opcode.MUL,  "/":  Opcode.DIV,
            "%":  Opcode.MOD,  "**": Opcode.EXP,
            "==": Opcode.EQ,   "!=": Opcode.NEQ,
            "<":  Opcode.LT,   ">":  Opcode.GT,
            "<=": Opcode.LE,   ">=": Opcode.GE,
            "&":  Opcode.AND,  "|":  Opcode.OR,
        }
        opcode = opcode_map.get(op)
        if opcode:
            self._emit(opcode, comment=op)
        else:
            self._emit(Opcode.POP)  # Unknown op — discard

    def _compile_unary(self, expr: Dict[str, Any]):
        op = expr.get("op", "")
        self._compile_expr(expr["operand"])
        if op == "!":
            self._emit(Opcode.NOT)
        elif op == "-":
            self._emit(Opcode.PUSH, 0)
            self._emit(Opcode.SWAP)
            self._emit(Opcode.SUB)

    def _compile_call(self, expr: Dict[str, Any]):
        name = expr.get("name", "")

        # Built-in functions
        builtins = {
            "sha256":            Opcode.SHA256,
            "compute_hash":      Opcode.SHA256,
            "validate_signature": Opcode.CALL,
            "update_ledger":     Opcode.SSTORE,
            "log":               Opcode.LOG,
        }

        if name in builtins:
            for arg in expr.get("args", []):
                self._compile_expr(arg)
            self._emit(builtins[name], comment=f"call builtin {name}")
            return

        # User-defined function call
        for arg in expr.get("args", []):
            self._compile_expr(arg)

        fn_label = f"__fn_{name}"
        call_idx = len(self._code)
        self._emit(Opcode.CALL, None, comment=f"call {name}")
        self._labels.mark_jump(call_idx, fn_label)

    # ── Emit Helper ───────────────────────────────────────────────────────────

    def _emit(self, opcode: int, *operands, comment: str = "") -> int:
        idx = len(self._code)
        self._code.append(Instruction(opcode=opcode, operands=list(operands), comment=comment))
        return idx

    # ── Disassembler ──────────────────────────────────────────────────────────

    @staticmethod
    def disassemble(bytecode: Bytecode) -> str:
        lines = []
        for i, instr in enumerate(bytecode):
            lines.append(f"{i:4d}: {instr}")
        return "\n".join(lines)
