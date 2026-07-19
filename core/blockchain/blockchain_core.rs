// blockchain_core.rs — SatoshiOS Blockchain Engine
//
// Top-level blockchain engine that wires together Block, Chain,
// Mempool, and Merkle tree utilities.  Acts as the single entry
// point for mining, transaction submission, and chain queries.

use crate::block::{Block, Transaction};
use crate::chain::{Chain, ChainError, ChainResult};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

// ─── Merkle Tree ────────────────────────────────────────────────────────────

/// A full Merkle tree built from leaf hashes.
pub struct MerkleTree {
    pub root: String,
    levels: Vec<Vec<String>>,
}

impl MerkleTree {
    pub fn build(leaves: &[String]) -> Self {
        if leaves.is_empty() {
            return Self {
                root: "0".repeat(64),
                levels: vec![],
            };
        }

        let mut current: Vec<String> = leaves.to_vec();
        let mut levels = vec![current.clone()];

        while current.len() > 1 {
            if current.len() % 2 != 0 {
                current.push(current.last().unwrap().clone());
            }
            let next: Vec<String> = current
                .chunks(2)
                .map(|pair| {
                    let mut h = Sha256::new();
                    h.update(format!("{}{}", pair[0], pair[1]));
                    format!("{:x}", h.finalize())
                })
                .collect();
            levels.push(next.clone());
            current = next;
        }

        Self {
            root: current[0].clone(),
            levels,
        }
    }

    /// Generate inclusion proof for leaf at position `index`.
    pub fn proof(&self, index: usize) -> Vec<(String, bool)> {
        let mut proof = Vec::new();
        let mut idx = index;

        for level in &self.levels[..self.levels.len().saturating_sub(1)] {
            let sibling_idx = if idx % 2 == 0 { idx + 1 } else { idx - 1 };
            let is_right = idx % 2 == 0;
            if sibling_idx < level.len() {
                proof.push((level[sibling_idx].clone(), is_right));
            }
            idx /= 2;
        }
        proof
    }

    /// Verify inclusion proof.
    pub fn verify_proof(leaf: &str, proof: &[(String, bool)], root: &str) -> bool {
        let mut hash = leaf.to_string();
        for (sibling, is_right) in proof {
            let mut h = Sha256::new();
            if *is_right {
                h.update(format!("{}{}", hash, sibling));
            } else {
                h.update(format!("{}{}", sibling, hash));
            }
            hash = format!("{:x}", h.finalize());
        }
        hash == root
    }
}

// ─── In-Memory Mempool ───────────────────────────────────────────────────────

/// Simple in-memory pending transaction pool.
pub struct InternalMempool {
    pub pending: HashMap<String, Transaction>,
    capacity: usize,
}

impl InternalMempool {
    pub fn new(capacity: usize) -> Self {
        Self {
            pending: HashMap::new(),
            capacity,
        }
    }

    pub fn add(&mut self, tx: Transaction) -> bool {
        if self.pending.len() >= self.capacity {
            return false;
        }
        self.pending.insert(tx.tx_id.clone(), tx);
        true
    }

    pub fn remove(&mut self, tx_id: &str) -> Option<Transaction> {
        self.pending.remove(tx_id)
    }

    /// Drain up to `count` transactions (highest nonce first).
    pub fn drain(&mut self, count: usize) -> Vec<Transaction> {
        let keys: Vec<String> = self
            .pending
            .keys()
            .take(count)
            .cloned()
            .collect();

        keys.iter()
            .filter_map(|k| self.pending.remove(k))
            .collect()
    }

    pub fn len(&self) -> usize {
        self.pending.len()
    }

    pub fn is_empty(&self) -> bool {
        self.pending.is_empty()
    }
}

// ─── Proof-of-Work Miner ────────────────────────────────────────────────────

/// Increments nonce until block hash meets difficulty target.
pub fn mine_pow(block: &mut Block) -> u64 {
    let target = "0".repeat(block.header.difficulty as usize);
    let mut attempts: u64 = 0;

    loop {
        block.update_hash();
        if block.hash.starts_with(&target) {
            println!(
                "[PoW] Mined block #{} — nonce: {}, attempts: {}, hash: {}",
                block.header.index, block.header.nonce, attempts, &block.hash[..16]
            );
            return attempts;
        }
        block.header.nonce += 1;
        attempts += 1;

        if attempts > 10_000_000 {
            panic!("PoW: mining timeout after {} attempts (limit: {})", attempts, 10_000_000);
        }
    }
}

// ─── BlockchainCore ─────────────────────────────────────────────────────────

/// Main blockchain engine — combines chain, mempool, and mining.
pub struct BlockchainCore {
    pub chain: Chain,
    pub mempool: InternalMempool,
    pub miner_address: String,
    pub difficulty: u32,
    pub block_reward: u64,
    /// Address → balance ledger.
    pub balances: HashMap<String, u64>,
}

impl BlockchainCore {
    pub fn new(miner_address: &str, difficulty: u32) -> Self {
        let mut core = Self {
            chain: Chain::new(),
            mempool: InternalMempool::new(10_000),
            miner_address: miner_address.to_string(),
            difficulty,
            block_reward: 50,
            balances: HashMap::new(),
        };
        // Credit genesis miner
        core.balances.insert("satoshi".to_string(), 1_000_000);
        core
    }

    /// Submit a transaction to the mempool.
    pub fn submit_transaction(&mut self, tx: Transaction) -> bool {
        // Basic balance check
        let balance = self.balances.get(&tx.from).copied().unwrap_or(0);
        if balance < tx.amount {
            println!("[Core] Rejected tx {}: insufficient balance", &tx.tx_id[..8]);
            return false;
        }
        let added = self.mempool.add(tx);
        if added {
            println!("[Core] Transaction accepted into mempool (pool size: {})", self.mempool.len());
        }
        added
    }

    /// Mine the next block with pending transactions.
    pub fn mine_next_block(&mut self) -> ChainResult<String> {
        let txs = self.mempool.drain(500);
        let prev_hash = self.chain.tip().ok_or(ChainError::EmptyChain)?.hash.clone();
        let index = self.chain.height();

        let mut block = Block::new(
            index,
            prev_hash,
            txs.clone(),
            0,
            self.difficulty,
            self.miner_address.clone(),
        );

        mine_pow(&mut block);
        let block_hash = block.hash.clone();

        // Apply transactions to balances
        for tx in &txs {
            let from_balance = self.balances.entry(tx.from.clone()).or_insert(0);
            *from_balance = from_balance.saturating_sub(tx.amount);
            let to_balance = self.balances.entry(tx.to.clone()).or_insert(0);
            *to_balance += tx.amount;
        }

        // Block reward
        *self.balances.entry(self.miner_address.clone()).or_insert(0) += self.block_reward;

        self.chain.add_block(block)?;
        println!(
            "[Core] Block #{} mined and added — {} txs, hash: {}",
            index,
            txs.len(),
            &block_hash[..16]
        );
        Ok(block_hash)
    }

    /// Current stats snapshot.
    pub fn stats(&self) -> CoreStats {
        let chain_stats = self.chain.stats();
        CoreStats {
            height: chain_stats.height,
            total_transactions: chain_stats.total_transactions,
            pending_transactions: self.mempool.len() as u64,
            tip_hash: chain_stats.tip_hash,
            difficulty: self.difficulty,
            miner: self.miner_address.clone(),
        }
    }
}

#[derive(Debug)]
pub struct CoreStats {
    pub height: u64,
    pub total_transactions: u64,
    pub pending_transactions: u64,
    pub tip_hash: String,
    pub difficulty: u32,
    pub miner: String,
}

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_tree_root() {
        let leaves: Vec<String> = (0..4).map(|i| format!("leaf{}", i)).collect();
        let tree = MerkleTree::build(&leaves);
        assert_eq!(tree.root.len(), 64);
    }

    #[test]
    fn test_merkle_proof_verify() {
        let leaves: Vec<String> = (0..4).map(|i| format!("leaf{}", i)).collect();
        let tree = MerkleTree::build(&leaves);
        let proof = tree.proof(0);
        assert!(MerkleTree::verify_proof("leaf0", &proof, &tree.root));
    }

    #[test]
    fn test_mempool_capacity() {
        let mut pool = InternalMempool::new(2);
        let tx1 = Transaction::new("a", "b", 1, 1);
        let tx2 = Transaction::new("a", "b", 2, 2);
        let tx3 = Transaction::new("a", "b", 3, 3);
        assert!(pool.add(tx1));
        assert!(pool.add(tx2));
        assert!(!pool.add(tx3)); // Over capacity
    }

    #[test]
    fn test_mine_difficulty_0() {
        let mut core = BlockchainCore::new("miner1", 0);
        let result = core.mine_next_block();
        assert!(result.is_ok());
        assert_eq!(core.chain.height(), 2);
    }

    #[test]
    fn test_transaction_balance_check() {
        let mut core = BlockchainCore::new("miner1", 0);
        // Unknown address has 0 balance
        let tx = Transaction::new("unknown", "bob", 999, 1);
        assert!(!core.submit_transaction(tx));
    }
}
