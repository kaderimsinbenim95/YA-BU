#!/usr/bin/env python3
"""
Hybrid Consensus Engine

Combines PoW (Proof of Work) and PoS (Proof of Stake) mechanisms
dynamically based on network health and security threats.
"""

import hashlib
import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


class ConsensusType(Enum):
    """Consensus mechanism types"""
    POW = "pow"              # Pure Proof of Work
    POS = "pos"              # Pure Proof of Stake
    HYBRID_50_50 = "hybrid_50_50"    # 50% PoW + 50% PoS
    HYBRID_70_30 = "hybrid_70_30"    # 70% PoS + 30% PoW


@dataclass
class NetworkMetrics:
    """Tracks network health metrics"""
    online_nodes: int
    total_nodes: int
    avg_latency_ms: float
    transaction_backlog: int
    threat_level: int  # 0-100
    recent_attacks: int
    
    def health_score(self) -> float:
        """Calculate network health score (0-100)"""
        node_health = (self.online_nodes / max(self.total_nodes, 1)) * 0.4 * 100
        latency_health = max(0, (1 - self.avg_latency_ms / 1000)) * 0.3 * 100
        backlog_health = max(0, (1 - self.transaction_backlog / 10000)) * 0.2 * 100
        threat_health = max(0, (1 - self.threat_level / 100)) * 0.1 * 100
        
        return node_health + latency_health + backlog_health + threat_health


@dataclass
class Block:
    """Represents a blockchain block"""
    index: int
    timestamp: float
    transactions: List[str]
    nonce: int
    hash: str = ""
    prev_hash: str = ""
    
    def to_bytes(self) -> bytes:
        """Convert block to bytes for hashing"""
        data = f"{self.index}{self.timestamp}{''.join(self.transactions)}{self.nonce}{self.prev_hash}"
        return data.encode('utf-8')
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of block"""
        return hashlib.sha256(self.to_bytes()).hexdigest()


class ProofOfWork:
    """Proof of Work implementation (SHA-256 based)"""
    
    def __init__(self, difficulty: int = 2):
        self.difficulty = difficulty
        self.min_difficulty = 1
        self.max_difficulty = 10
    
    def solve(self, block: Block) -> Block:
        """Solve PoW puzzle (mine block)"""
        target = '0' * self.difficulty
        attempts = 0
        start_time = time.time()
        
        while True:
            block.hash = block.calculate_hash()
            
            if block.hash.startswith(target):
                elapsed = time.time() - start_time
                print(f"[PoW] Block mined! Nonce: {block.nonce}, Attempts: {attempts}, Time: {elapsed:.2f}s")
                return block
            
            block.nonce += 1
            attempts += 1
            
            # Safety check to prevent infinite loops
            if attempts > 1000000:
                raise RuntimeError("PoW solving timeout")
    
    def verify(self, block: Block) -> bool:
        """Verify PoW"""
        target = '0' * self.difficulty
        block_hash = block.calculate_hash()
        return block_hash.startswith(target)
    
    def adjust_difficulty(self, blocks: List[Block]) -> int:
        """Adjust difficulty based on recent block times"""
        if len(blocks) < 2:
            return self.difficulty
        
        target_block_time = 10  # 10 seconds
        recent_blocks = blocks[-10:]
        
        total_time = recent_blocks[-1].timestamp - recent_blocks[0].timestamp
        actual_block_time = total_time / len(recent_blocks)
        
        if actual_block_time > target_block_time:
            # Reduce difficulty
            new_difficulty = max(self.min_difficulty, self.difficulty - 1)
        else:
            # Increase difficulty
            new_difficulty = min(self.max_difficulty, self.difficulty + 1)
        
        self.difficulty = new_difficulty
        return new_difficulty


class ProofOfStake:
    """Proof of Stake implementation"""
    
    def __init__(self, min_stake: int = 32):
        self.min_stake = min_stake
        self.validators: Dict[str, int] = {}  # address -> stake
        self.slashing_penalties: Dict[str, int] = {}
    
    def add_validator(self, address: str, stake: int):
        """Add validator to the set"""
        if stake < self.min_stake:
            raise ValueError(f"Stake must be >= {self.min_stake}")
        self.validators[address] = stake
    
    def remove_validator(self, address: str):
        """Remove validator from the set"""
        if address in self.validators:
            del self.validators[address]
    
    def select_validator(self, slot: int) -> Optional[str]:
        """Select validator for current slot using stake-weighted randomness"""
        if not self.validators:
            return None
        
        total_stake = sum(self.validators.values())
        
        # Weighted random selection
        import random
        random.seed(slot)  # Deterministic based on slot
        
        # Create weighted list
        weighted_validators = []
        for address, stake in self.validators.items():
            weight = stake / total_stake
            weighted_validators.append((address, weight))
        
        # Select with probability proportional to stake
        r = random.random()
        cumulative = 0
        
        for address, weight in weighted_validators:
            cumulative += weight
            if r < cumulative:
                return address
        
        return list(self.validators.keys())[0]
    
    def validate_block(self, block: Block, proposer: str, signature: str) -> bool:
        """Validate block proposed by validator"""
        if proposer not in self.validators:
            return False
        
        # Simplified signature verification
        expected_signature = hashlib.sha256(
            (block.to_bytes() + proposer.encode()).encode()
        ).hexdigest()
        
        return signature == expected_signature[:16]
    
    def slash_validator(self, address: str, penalty_percentage: int = 20):
        """Slash validator for malicious behavior"""
        if address in self.validators:
            penalty = int(self.validators[address] * penalty_percentage / 100)
            self.validators[address] -= penalty
            self.slashing_penalties[address] = self.slashing_penalties.get(address, 0) + penalty
            print(f"[PoS] Validator {address} slashed: -{penalty} tokens")


class HybridConsensus:
    """Hybrid PoW + PoS consensus engine"""
    
    def __init__(self):
        self.pow = ProofOfWork(difficulty=2)
        self.pos = ProofOfStake(min_stake=32)
        self.chain: List[Block] = []
        self.pending_blocks: List[Block] = []
        self.consensus_type = ConsensusType.POW
        self.metrics: Optional[NetworkMetrics] = None
    
    def update_metrics(self, metrics: NetworkMetrics):
        """Update network metrics and adjust consensus type"""
        self.metrics = metrics
        self._select_consensus_type()
    
    def _select_consensus_type(self):
        """Select consensus type based on network health"""
        if not self.metrics:
            return
        
        health = self.metrics.health_score()
        threat_level = self.metrics.threat_level
        
        # Selection logic
        if health >= 90 and threat_level < 30 and self.metrics.recent_attacks == 0:
            self.consensus_type = ConsensusType.POW
            print(f"[Consensus] Selected: PoW (Network Health: {health:.1f})")
        
        elif health >= 70 and threat_level < 50:
            self.consensus_type = ConsensusType.HYBRID_50_50
            print(f"[Consensus] Selected: Hybrid 50/50 (Network Health: {health:.1f})")
        
        elif health >= 50 and threat_level < 70:
            self.consensus_type = ConsensusType.HYBRID_70_30
            print(f"[Consensus] Selected: Hybrid 70/30 PoS (Network Health: {health:.1f})")
        
        else:
            self.consensus_type = ConsensusType.POS
            print(f"[Consensus] Selected: PoS Emergency Mode (Network Health: {health:.1f})")
    
    def create_block(self, transactions: List[str], proposer: Optional[str] = None) -> Block:
        """Create a new block"""
        prev_hash = self.chain[-1].hash if self.chain else "genesis"
        
        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            transactions=transactions,
            nonce=0,
            prev_hash=prev_hash
        )
        
        return block
    
    def mine_block(self, block: Block, proposer: Optional[str] = None) -> bool:
        """Mine/create block based on selected consensus type"""
        if self.consensus_type == ConsensusType.POW:
            return self._mine_pow_block(block)
        
        elif self.consensus_type == ConsensusType.POS:
            return self._mine_pos_block(block, proposer)
        
        elif self.consensus_type in [ConsensusType.HYBRID_50_50, ConsensusType.HYBRID_70_30]:
            return self._mine_hybrid_block(block, proposer)
        
        return False
    
    def _mine_pow_block(self, block: Block) -> bool:
        """Mine block using PoW"""
        print("[Mining] Starting PoW mining...")
        try:
            block = self.pow.solve(block)
            self.chain.append(block)
            return True
        except Exception as e:
            print(f"[Error] PoW mining failed: {e}")
            return False
    
    def _mine_pos_block(self, block: Block, proposer: Optional[str] = None) -> bool:
        """Create block using PoS"""
        print("[Mining] Starting PoS validation...")
        
        if not proposer:
            # Select validator
            slot = len(self.chain)
            proposer = self.pos.select_validator(slot)
        
        if not proposer:
            print("[Error] No validators available")
            return False
        
        # Sign block
        signature = hashlib.sha256(
            (block.to_bytes() + proposer.encode()).encode()
        ).hexdigest()[:16]
        
        # Validate
        if self.pos.validate_block(block, proposer, signature):
            block.hash = block.calculate_hash()
            self.chain.append(block)
            print(f"[PoS] Block #{block.index} created by validator {proposer}")
            return True
        
        return False
    
    def _mine_hybrid_block(self, block: Block, proposer: Optional[str] = None) -> bool:
        """Mine block using hybrid consensus"""
        print("[Mining] Starting hybrid consensus...")
        
        if self.consensus_type == ConsensusType.HYBRID_50_50:
            pow_weight = 0.5
            pos_weight = 0.5
        else:  # HYBRID_70_30
            pow_weight = 0.3
            pos_weight = 0.7
        
        # PoW portion
        original_difficulty = self.pow.difficulty
        self.pow.difficulty = max(1, int(self.pow.difficulty * pow_weight))
        
        try:
            block = self.pow.solve(block)
        except:
            pass
        finally:
            self.pow.difficulty = original_difficulty
        
        # PoS portion
        if not proposer:
            slot = len(self.chain)
            proposer = self.pos.select_validator(slot)
        
        if proposer:
            signature = hashlib.sha256(
                (block.to_bytes() + proposer.encode()).encode()
            ).hexdigest()[:16]
            
            if self.pos.validate_block(block, proposer, signature):
                block.hash = block.calculate_hash()
                self.chain.append(block)
                print(f"[Hybrid] Block #{block.index} accepted")
                return True
        
        return False
    
    def get_chain_length(self) -> int:
        """Get blockchain length"""
        return len(self.chain)
    
    def get_latest_block(self) -> Optional[Block]:
        """Get latest block in chain"""
        return self.chain[-1] if self.chain else None


if __name__ == "__main__":
    # Example usage
    consensus = HybridConsensus()
    
    # Add validators
    consensus.pos.add_validator("validator1", 100)
    consensus.pos.add_validator("validator2", 80)
    consensus.pos.add_validator("validator3", 60)
    
    # Simulate network metrics
    metrics = NetworkMetrics(
        online_nodes=95,
        total_nodes=100,
        avg_latency_ms=50,
        transaction_backlog=100,
        threat_level=20,
        recent_attacks=0
    )
    
    consensus.update_metrics(metrics)
    
    # Create and mine blocks
    for i in range(3):
        block = consensus.create_block([f"tx_{j}" for j in range(5)])
        consensus.mine_block(block)
    
    print(f"\nBlockchain length: {consensus.get_chain_length()}")
