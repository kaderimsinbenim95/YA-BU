// block.rs — SatoshiOS Block Data Structure
//
// Defines the fundamental Block type used across the blockchain,
// including Merkle tree root computation and serialization.

use std::time::{SystemTime, UNIX_EPOCH};
use sha2::{Sha256, Digest};
use serde::{Serialize, Deserialize};

/// A single transaction stored inside a block.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Transaction {
    pub tx_id: String,
    pub from: String,
    pub to: String,
    pub amount: u64,
    pub gas_limit: u64,
    pub gas_price: u64,
    pub nonce: u64,
    pub data: Vec<u8>,     // Smart contract calldata
    pub signature: String,
    pub timestamp: u64,
}

impl Transaction {
    pub fn new(from: &str, to: &str, amount: u64, nonce: u64) -> Self {
        let timestamp = current_timestamp();
        let tx_id = Self::compute_id(from, to, amount, nonce, timestamp);
        Self {
            tx_id,
            from: from.to_string(),
            to: to.to_string(),
            amount,
            gas_limit: 21_000,
            gas_price: 1,
            nonce,
            data: vec![],
            signature: String::new(),
            timestamp,
        }
    }

    fn compute_id(from: &str, to: &str, amount: u64, nonce: u64, ts: u64) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!("{}{}{}{}{}", from, to, amount, nonce, ts));
        format!("{:x}", hasher.finalize())
    }

    pub fn hash(&self) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!(
            "{}{}{}{}{}{}",
            self.from, self.to, self.amount, self.nonce, self.timestamp, self.tx_id
        ));
        format!("{:x}", hasher.finalize())
    }
}

/// Block header — contains metadata and proof fields.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockHeader {
    pub version: u32,
    pub index: u64,
    pub timestamp: u64,
    pub prev_hash: String,
    pub merkle_root: String,
    pub nonce: u64,
    pub difficulty: u32,
    pub miner: String,
    pub state_root: String,   // Merkle Patricia Trie root of world state
}

impl BlockHeader {
    pub fn hash(&self) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!(
            "{}{}{}{}{}{}{}{}{}",
            self.version,
            self.index,
            self.timestamp,
            self.prev_hash,
            self.merkle_root,
            self.nonce,
            self.difficulty,
            self.miner,
            self.state_root,
        ));
        format!("{:x}", hasher.finalize())
    }
}

/// A full block: header + transactions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    pub header: BlockHeader,
    pub transactions: Vec<Transaction>,
    pub hash: String,
}

impl Block {
    /// Create a new block (hash is computed immediately).
    pub fn new(
        index: u64,
        prev_hash: String,
        transactions: Vec<Transaction>,
        nonce: u64,
        difficulty: u32,
        miner: String,
    ) -> Self {
        let merkle_root = compute_merkle_root(&transactions);
        let header = BlockHeader {
            version: 1,
            index,
            timestamp: current_timestamp(),
            prev_hash,
            merkle_root,
            nonce,
            difficulty,
            miner,
            state_root: String::from("0000000000000000000000000000000000000000000000000000000000000000"),
        };
        let hash = header.hash();
        Self { header, transactions, hash }
    }

    /// Recompute and update the block hash.
    pub fn update_hash(&mut self) {
        self.hash = self.header.hash();
    }

    /// Check if hash satisfies the difficulty target (leading zeros).
    pub fn meets_difficulty(&self) -> bool {
        let target = "0".repeat(self.header.difficulty as usize);
        self.hash.starts_with(&target)
    }

    /// Number of transactions in the block.
    pub fn tx_count(&self) -> usize {
        self.transactions.len()
    }
}

/// Compute Merkle root of a list of transactions.
/// Returns all-zeros hash for empty transaction list.
pub fn compute_merkle_root(txs: &[Transaction]) -> String {
    if txs.is_empty() {
        return "0000000000000000000000000000000000000000000000000000000000000000".to_string();
    }

    let mut hashes: Vec<String> = txs.iter().map(|tx| tx.hash()).collect();

    while hashes.len() > 1 {
        if hashes.len() % 2 != 0 {
            hashes.push(hashes.last().unwrap().clone()); // Duplicate last if odd
        }

        let mut new_level = Vec::new();
        for chunk in hashes.chunks(2) {
            let mut hasher = Sha256::new();
            hasher.update(format!("{}{}", chunk[0], chunk[1]));
            new_level.push(format!("{:x}", hasher.finalize()));
        }
        hashes = new_level;
    }

    hashes.remove(0)
}

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transaction_hash_deterministic() {
        let tx = Transaction::new("alice", "bob", 100, 1);
        assert_eq!(tx.hash(), tx.hash());
    }

    #[test]
    fn test_merkle_root_empty() {
        let root = compute_merkle_root(&[]);
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_merkle_root_single() {
        let tx = Transaction::new("alice", "bob", 100, 1);
        let root = compute_merkle_root(&[tx]);
        assert_eq!(root.len(), 64);
    }

    #[test]
    fn test_block_creation() {
        let txs = vec![Transaction::new("alice", "bob", 50, 1)];
        let block = Block::new(1, "prevhash".to_string(), txs, 0, 2, "miner1".to_string());
        assert_eq!(block.header.index, 1);
        assert_eq!(block.tx_count(), 1);
    }

    #[test]
    fn test_block_hash_length() {
        let block = Block::new(0, "genesis".to_string(), vec![], 0, 0, "genesis".to_string());
        assert_eq!(block.hash.len(), 64);
    }
}
