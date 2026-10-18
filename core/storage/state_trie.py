#!/usr/bin/env python3
"""
State Trie — Merkle Patricia Trie for World State

Implements a simplified Merkle Patricia Trie (MPT) that tracks account
states and produces a cryptographic root hash — the `state_root` stored
in every block header.

Node types:
  - LeafNode    — stores a key-value pair at a path terminus
  - BranchNode  — 16-way branch (hex digits 0-f) + optional value
  - ExtensionNode — shared path prefix pointing to a child
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple, Union


# ─── Nibble Utilities ─────────────────────────────────────────────────────────

def to_nibbles(key: bytes) -> List[int]:
    """Convert bytes to list of nibbles (0-15)."""
    nibbles = []
    for byte in key:
        nibbles.append((byte >> 4) & 0xF)
        nibbles.append(byte & 0xF)
    return nibbles


def nibbles_to_bytes(nibbles: List[int]) -> bytes:
    """
    Convert a nibble list back to bytes.

    If the length is odd, a leading zero nibble is prepended to make the
    total even — this is consistent with the Compact/Hex-Prefix encoding
    used in Ethereum MPT leaf/extension nodes (EIP-8).
    """
    if len(nibbles) % 2 != 0:
        nibbles = [0] + nibbles
    result = bytearray()
    for i in range(0, len(nibbles), 2):
        result.append((nibbles[i] << 4) | nibbles[i + 1])
    return bytes(result)


def common_prefix_length(a: List[int], b: List[int]) -> int:
    length = min(len(a), len(b))
    for i in range(length):
        if a[i] != b[i]:
            return i
    return length


# ─── Trie Nodes ───────────────────────────────────────────────────────────────

class TrieNode:
    """Base class for all trie node types."""

    def hash(self) -> str:
        encoded = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict:
        raise NotImplementedError


class LeafNode(TrieNode):
    def __init__(self, path: List[int], value: Any):
        self.path = path
        self.value = value

    def to_dict(self) -> dict:
        return {"type": "leaf", "path": self.path, "value": self.value}


class BranchNode(TrieNode):
    def __init__(self):
        self.children: List[Optional[TrieNode]] = [None] * 16
        self.value: Any = None

    def to_dict(self) -> dict:
        children_hashes = [
            c.hash() if c else None for c in self.children
        ]
        return {"type": "branch", "children": children_hashes, "value": self.value}


class ExtensionNode(TrieNode):
    def __init__(self, path: List[int], child: TrieNode):
        self.path  = path
        self.child = child

    def to_dict(self) -> dict:
        return {
            "type": "extension",
            "path": self.path,
            "child": self.child.hash(),
        }


# ─── MerklePatriciaTrie ───────────────────────────────────────────────────────

class MerklePatriciaTrie:
    """
    Simplified Merkle Patricia Trie.

    Stores string-keyed, JSON-serialisable values.
    Keys are converted to nibble paths via SHA-256 for uniform distribution.
    """

    def __init__(self):
        self._root: Optional[TrieNode] = None
        self._cache: Dict[str, Any] = {}  # raw key → value cache for fast lookup

    # ── Public API ─────────────────────────────────────────────────────────────

    def put(self, key: str, value: Any):
        """Insert or update a key-value pair."""
        self._cache[key] = value
        nibble_key = self._key_to_nibbles(key)
        self._root = self._insert(self._root, nibble_key, value)

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value by key (cache-first)."""
        return self._cache.get(key)

    def delete(self, key: str):
        """Remove a key from the trie."""
        if key not in self._cache:
            return
        del self._cache[key]
        nibble_key = self._key_to_nibbles(key)
        self._root = self._delete(self._root, nibble_key)

    def root_hash(self) -> str:
        """Return the Merkle root hash of the current state."""
        if self._root is None:
            return "0" * 64
        return self._root.hash()

    def contains(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)

    # ── Insertion ─────────────────────────────────────────────────────────────

    def _insert(
        self,
        node: Optional[TrieNode],
        nibbles: List[int],
        value: Any,
    ) -> TrieNode:
        if node is None:
            return LeafNode(nibbles, value)

        if isinstance(node, LeafNode):
            return self._insert_into_leaf(node, nibbles, value)

        if isinstance(node, ExtensionNode):
            return self._insert_into_extension(node, nibbles, value)

        if isinstance(node, BranchNode):
            return self._insert_into_branch(node, nibbles, value)

        raise ValueError(f"Unknown node type: {type(node)}")

    def _insert_into_leaf(self, leaf: LeafNode, nibbles: List[int], value: Any) -> TrieNode:
        prefix_len = common_prefix_length(leaf.path, nibbles)

        if prefix_len == len(leaf.path) == len(nibbles):
            # Same path — update value
            return LeafNode(leaf.path, value)

        # Create a branch to split the paths
        branch = BranchNode()

        # Existing leaf continuation
        if prefix_len < len(leaf.path):
            leaf_idx = leaf.path[prefix_len]
            branch.children[leaf_idx] = LeafNode(leaf.path[prefix_len + 1:], leaf.value)
        else:
            branch.value = leaf.value

        # New value continuation
        if prefix_len < len(nibbles):
            new_idx = nibbles[prefix_len]
            branch.children[new_idx] = LeafNode(nibbles[prefix_len + 1:], value)
        else:
            branch.value = value

        # Wrap in extension if there's a shared prefix
        if prefix_len > 0:
            return ExtensionNode(nibbles[:prefix_len], branch)

        return branch

    def _insert_into_extension(self, ext: ExtensionNode, nibbles: List[int], value: Any) -> TrieNode:
        prefix_len = common_prefix_length(ext.path, nibbles)

        if prefix_len == len(ext.path):
            # Full prefix match — recurse into child
            new_child = self._insert(ext.child, nibbles[prefix_len:], value)
            return ExtensionNode(ext.path, new_child)

        # Partial match — need to split
        branch = BranchNode()

        ext_idx = ext.path[prefix_len]
        if len(ext.path) - prefix_len - 1 > 0:
            branch.children[ext_idx] = ExtensionNode(ext.path[prefix_len + 1:], ext.child)
        else:
            branch.children[ext_idx] = ext.child

        new_idx = nibbles[prefix_len]
        branch.children[new_idx] = LeafNode(nibbles[prefix_len + 1:], value)

        if prefix_len > 0:
            return ExtensionNode(nibbles[:prefix_len], branch)
        return branch

    def _insert_into_branch(self, branch: BranchNode, nibbles: List[int], value: Any) -> TrieNode:
        if not nibbles:
            branch.value = value
            return branch

        idx = nibbles[0]
        branch.children[idx] = self._insert(branch.children[idx], nibbles[1:], value)
        return branch

    # ── Deletion ──────────────────────────────────────────────────────────────

    def _delete(self, node: Optional[TrieNode], nibbles: List[int]) -> Optional[TrieNode]:
        if node is None:
            return None

        if isinstance(node, LeafNode):
            if node.path == nibbles:
                return None
            return node

        if isinstance(node, BranchNode):
            if not nibbles:
                node.value = None
            else:
                idx = nibbles[0]
                node.children[idx] = self._delete(node.children[idx], nibbles[1:])
            # Compact branch if only one child remains
            return self._compact_branch(node)

        if isinstance(node, ExtensionNode):
            prefix_len = common_prefix_length(node.path, nibbles)
            if prefix_len < len(node.path):
                return node  # Key not in this subtree
            new_child = self._delete(node.child, nibbles[prefix_len:])
            if new_child is None:
                return None
            return ExtensionNode(node.path, new_child)

        return node

    def _compact_branch(self, branch: BranchNode) -> Optional[TrieNode]:
        non_null = [(i, c) for i, c in enumerate(branch.children) if c is not None]

        if not non_null and branch.value is None:
            return None

        if len(non_null) == 1 and branch.value is None:
            idx, child = non_null[0]
            if isinstance(child, LeafNode):
                return LeafNode([idx] + child.path, child.value)
            return ExtensionNode([idx], child)

        return branch

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _key_to_nibbles(key: str) -> List[int]:
        """Hash key to 32 bytes and convert to nibbles for uniform distribution."""
        hashed = hashlib.sha256(key.encode()).digest()
        return to_nibbles(hashed)


# ─── AccountStateTrie ──────────────────────────────────────────────────────────

class AccountStateTrie(MerklePatriciaTrie):
    """
    Specialised trie for Ethereum-style world state.
    Each account stores: balance, nonce, code_hash, storage_root.
    """

    def get_account(self, address: str) -> dict:
        return self.get(address) or {
            "address": address, "balance": 0, "nonce": 0,
            "code_hash": "", "storage_root": "0" * 64,
        }

    def update_balance(self, address: str, delta: int):
        acc = self.get_account(address)
        acc["balance"] = max(0, acc["balance"] + delta)
        self.put(address, acc)

    def increment_nonce(self, address: str):
        acc = self.get_account(address)
        acc["nonce"] += 1
        self.put(address, acc)

    def set_contract_code(self, address: str, code_hash: str):
        acc = self.get_account(address)
        acc["code_hash"] = code_hash
        self.put(address, acc)

    def apply_transfer(self, from_addr: str, to_addr: str, amount: int) -> bool:
        sender = self.get_account(from_addr)
        if sender["balance"] < amount:
            return False
        self.update_balance(from_addr, -amount)
        self.update_balance(to_addr, amount)
        self.increment_nonce(from_addr)
        return True
