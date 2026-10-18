# ⚙️ Hybrid Consensus Mechanism (PoW + PoS)

## 1. Overview

SatoshiOS-AI-Blockchain, **Proof of Work** (PoW) ve **Proof of Stake** (PoS) mekanizmalarını dinamik olarak birleştiren hibrit bir konsensus sistemi kullanır.

### Why Hybrid?

| Aspect | PoW | PoS | Hybrid |
|--------|-----|-----|--------|
| Security | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Energy | ❌ High | ✅ Low | ⚖️ Medium |
| Scalability | ❌ Low | ✅ High | ⚖️ Medium-High |
| Decentralization | ✅ High | ❓ Medium | ✅ High |
| Finality | ❌ Probabilistic | ✅ Fast | ✅ Fast & Secure |

---

## 2. Consensus Mechanism Selection

### 2.1 Dynamic Selector Algorithm

```
INPUT: Network Health Metrics
├─ Node Count
├─ Average Latency
├─ Transaction Backlog
├─ Security Threat Level
└─ Recent Block Times

ALGORITHM:
1. Calculate network_health_score (0-100)
2. Check AI security level
3. Evaluate recent attack history
4. Apply selection rules
5. OUTPUT: Consensus Type
```

### 2.2 Selection Logic

```
if network_health_score >= 90 AND no_recent_attacks {
    // Primary: PoW (Most Secure)
    ConsensusType = PoW
    difficulty = adaptive_difficulty()
    
} else if network_health_score >= 70 AND low_threat_level {
    // Balanced: Hybrid (50% PoW + 50% PoS)
    ConsensusType = Hybrid
    pow_weight = 0.5
    pos_weight = 0.5
    
} else if network_health_score >= 50 AND medium_threat_level {
    // Lean toward PoS: Hybrid (30% PoW + 70% PoS)
    ConsensusType = Hybrid
    pow_weight = 0.3
    pos_weight = 0.7
    
} else {
    // Emergency: Pure PoS (Fast Finality)
    ConsensusType = PoS
    minimum_stake = 32 tokens
    validator_slashing = true
}
```

---

## 3. Proof of Work (PoW)

### PoW Algorithm (SHA-256)

```python
def solve_pow(block, difficulty):
    nonce = 0
    while True:
        block.nonce = nonce
        hash = sha256(block.to_bytes())
        
        if count_leading_zeros(hash) >= difficulty:
            return block
        
        nonce += 1
```

---

## 4. Proof of Stake (PoS)

### Validator Selection

```python
def select_validator(stakers, slot):
    valid_stakers = [s for s in stakers if s.stake >= 32]
    total_stake = sum(s.stake for s in valid_stakers)
    
    weights = [s.stake / total_stake for s in valid_stakers]
    validator = random_weighted_choice(valid_stakers, weights, slot)
    
    return validator
```

---

## 5. Performance Metrics

| Metric | PoW | PoS | Hybrid |
|--------|-----|-----|--------|
| Block Time | 10min | 6sec | 8sec |
| Finality | ~60min | ~6sec | ~12sec |
| Throughput | 7 TPS | 1000 TPS | 500 TPS |
| Energy/Block | 600 MJ | 0.01 MJ | 200 MJ |

---

**Version**: 2.0  
**Status**: Active Development

---

## 6. Storage Integration (v2.0)

Every time a block is accepted by the consensus engine it is:

1. Persisted by `LevelDBStore.apply_block()` — atomic write of block + all transactions
2. State trie root recomputed by `AccountStateTrie` — account transfers applied
3. New `state_root` stored in the block header

```
Consensus Accepts Block
       ↓
LevelDBStore.apply_block(block)
       ↓
AccountStateTrie.apply_transfer(from, to, amount) × N
       ↓
state_root = AccountStateTrie.root_hash()
       ↓
Block header.state_root updated
       ↓
Tip hash + height saved in metadata
```

---

## 7. Mempool ↔ Consensus Integration (v2.0)

```
New Transaction Arrives
       ↓
Mempool.add(tx, account_nonce)   ← validates nonce, gas price
       ↓
Consensus.mine_next_block()
  → Mempool.select_for_block(max_gas, max_txs)
  → Ordered by gas_price DESC, nonce ASC per sender
       ↓
Block mined → Mempool.remove_batch(mined_tx_ids)
```

---

## 8. P2P Block Propagation (v2.0)

New blocks discovered via gossip are validated through the full
consensus pipeline before being appended to the chain:

```
GossipProtocol receives BLOCK_DATA
       ↓
Chain.validate_block(block)
  - Index continuity
  - prev_hash linkage
  - Hash integrity
  - PoW difficulty
  - Merkle root
       ↓
If valid → Chain.add_block(block)
         → LevelDBStore.apply_block(block)
         → GossipProtocol re-announces to other peers
If invalid → Discard
```
