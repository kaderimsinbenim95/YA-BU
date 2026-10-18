// chain.rs — SatoshiOS Chain Management
//
// Manages the blockchain: genesis block creation, block appending,
// chain validation, fork resolution (longest chain rule), and reorgs.

use crate::block::{Block, Transaction, compute_merkle_root};
use std::collections::HashMap;

/// Result type for chain operations.
pub type ChainResult<T> = Result<T, ChainError>;

#[derive(Debug)]
pub enum ChainError {
    InvalidBlock(String),
    InvalidHash(String),
    InvalidPrevHash(String),
    InvalidIndex(String),
    EmptyChain,
    BlockNotFound(String),
    ForkTooShort,
}

impl std::fmt::Display for ChainError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ChainError::InvalidBlock(msg) => write!(f, "InvalidBlock: {}", msg),
            ChainError::InvalidHash(msg) => write!(f, "InvalidHash: {}", msg),
            ChainError::InvalidPrevHash(msg) => write!(f, "InvalidPrevHash: {}", msg),
            ChainError::InvalidIndex(msg) => write!(f, "InvalidIndex: {}", msg),
            ChainError::EmptyChain => write!(f, "Chain is empty"),
            ChainError::BlockNotFound(hash) => write!(f, "Block not found: {}", hash),
            ChainError::ForkTooShort => write!(f, "Fork chain is shorter than main chain"),
        }
    }
}

/// The blockchain — ordered list of validated blocks.
pub struct Chain {
    /// The canonical main chain (ordered by index).
    pub blocks: Vec<Block>,
    /// Index from block hash → block index for fast lookup.
    block_index: HashMap<String, u64>,
    /// Pending fork candidates (block hash → chain).
    forks: HashMap<String, Vec<Block>>,
}

impl Chain {
    /// Create a new chain with a genesis block.
    pub fn new() -> Self {
        let mut chain = Self {
            blocks: Vec::new(),
            block_index: HashMap::new(),
            forks: HashMap::new(),
        };
        chain.create_genesis();
        chain
    }

    /// Build and append the genesis block.
    fn create_genesis(&mut self) {
        let genesis = Block::new(
            0,
            "0000000000000000000000000000000000000000000000000000000000000000".to_string(),
            vec![],
            0,
            0,
            "satoshi".to_string(),
        );
        println!("[Chain] Genesis block created: {}", genesis.hash);
        self.block_index.insert(genesis.hash.clone(), 0);
        self.blocks.push(genesis);
    }

    /// Append a validated block to the chain.
    pub fn add_block(&mut self, block: Block) -> ChainResult<()> {
        self.validate_block(&block)?;
        self.block_index.insert(block.hash.clone(), block.header.index);
        self.blocks.push(block);
        Ok(())
    }

    /// Validate a candidate block against chain rules.
    pub fn validate_block(&self, block: &Block) -> ChainResult<()> {
        let tip = self.tip().ok_or(ChainError::EmptyChain)?;

        // Index must be sequential
        if block.header.index != tip.header.index + 1 {
            return Err(ChainError::InvalidIndex(format!(
                "Expected {}, got {}",
                tip.header.index + 1,
                block.header.index
            )));
        }

        // prev_hash must match tip
        if block.header.prev_hash != tip.hash {
            return Err(ChainError::InvalidPrevHash(format!(
                "Expected {}, got {}",
                tip.hash, block.header.prev_hash
            )));
        }

        // Hash must be consistent with header
        let expected_hash = block.header.hash();
        if block.hash != expected_hash {
            return Err(ChainError::InvalidHash(format!(
                "Stored hash {} ≠ computed {}",
                block.hash, expected_hash
            )));
        }

        // PoW difficulty check
        if block.header.difficulty > 0 && !block.meets_difficulty() {
            return Err(ChainError::InvalidBlock(format!(
                "Hash {} does not meet difficulty {}",
                block.hash, block.header.difficulty
            )));
        }

        // Merkle root check
        let expected_merkle = compute_merkle_root(&block.transactions);
        if block.header.merkle_root != expected_merkle {
            return Err(ChainError::InvalidBlock("Merkle root mismatch".to_string()));
        }

        Ok(())
    }

    /// Validate the entire chain from genesis.
    pub fn validate_chain(&self) -> ChainResult<()> {
        if self.blocks.is_empty() {
            return Err(ChainError::EmptyChain);
        }

        for i in 1..self.blocks.len() {
            let block = &self.blocks[i];
            let prev = &self.blocks[i - 1];

            // Index continuity
            if block.header.index != prev.header.index + 1 {
                return Err(ChainError::InvalidIndex(format!(
                    "Block {} has index {}, expected {}",
                    i,
                    block.header.index,
                    prev.header.index + 1
                )));
            }

            // Hash linkage
            if block.header.prev_hash != prev.hash {
                return Err(ChainError::InvalidPrevHash(format!(
                    "Block {} prev_hash mismatch",
                    i
                )));
            }

            // Hash integrity
            let expected = block.header.hash();
            if block.hash != expected {
                return Err(ChainError::InvalidHash(format!(
                    "Block {} hash mismatch",
                    i
                )));
            }
        }

        Ok(())
    }

    /// Get the current chain tip (last block).
    pub fn tip(&self) -> Option<&Block> {
        self.blocks.last()
    }

    /// Get block by hash.
    pub fn get_block_by_hash(&self, hash: &str) -> Option<&Block> {
        let idx = self.block_index.get(hash)?;
        self.blocks.get(*idx as usize)
    }

    /// Get block by index.
    pub fn get_block_by_index(&self, index: u64) -> Option<&Block> {
        self.blocks.get(index as usize)
    }

    /// Current chain length.
    pub fn height(&self) -> u64 {
        self.blocks.len() as u64
    }

    /// Register a fork candidate.  If fork is longer than main chain,
    /// trigger a reorg (longest-chain rule).
    pub fn handle_fork(&mut self, fork_chain: Vec<Block>) -> ChainResult<()> {
        if fork_chain.is_empty() {
            return Ok(());
        }

        // Validate fork internally
        for i in 1..fork_chain.len() {
            let b = &fork_chain[i];
            let p = &fork_chain[i - 1];
            if b.header.prev_hash != p.hash {
                return Err(ChainError::InvalidPrevHash(format!(
                    "Fork block {} prev_hash mismatch",
                    i
                )));
            }
        }

        let fork_len = fork_chain.len() as u64;
        if fork_len <= self.height() {
            return Err(ChainError::ForkTooShort);
        }

        println!(
            "[Chain] ⚠️  Reorganisation: switching from height {} to {}",
            self.height(),
            fork_len
        );

        // Rebuild index
        self.block_index.clear();
        for block in &fork_chain {
            self.block_index
                .insert(block.hash.clone(), block.header.index);
        }
        self.blocks = fork_chain;
        Ok(())
    }

    /// Summary stats for logging / API.
    pub fn stats(&self) -> ChainStats {
        let total_txs: usize = self.blocks.iter().map(|b| b.tx_count()).sum();
        ChainStats {
            height: self.height(),
            total_transactions: total_txs as u64,
            tip_hash: self.tip().map(|b| b.hash.clone()).unwrap_or_default(),
            tip_timestamp: self.tip().map(|b| b.header.timestamp).unwrap_or(0),
        }
    }
}

impl Default for Chain {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug)]
pub struct ChainStats {
    pub height: u64,
    pub total_transactions: u64,
    pub tip_hash: String,
    pub tip_timestamp: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Starting nonce for test blocks; real blocks increment nonce during PoW.
    const INITIAL_NONCE: u64 = 0;

    fn make_block(index: u64, prev_hash: &str, nonce: u64) -> Block {
        Block::new(
            index,
            prev_hash.to_string(),
            vec![],
            nonce,
            0,
            "miner".to_string(),
        )
    }

    #[test]
    fn test_genesis_created() {
        let chain = Chain::new();
        assert_eq!(chain.height(), 1);
        assert_eq!(chain.blocks[0].header.index, 0);
    }

    #[test]
    fn test_add_valid_block() {
        let mut chain = Chain::new();
        let tip_hash = chain.tip().unwrap().hash.clone();
        let block = make_block(1, &tip_hash, INITIAL_NONCE);
        assert!(chain.add_block(block).is_ok());
        assert_eq!(chain.height(), 2);
    }

    #[test]
    fn test_invalid_prev_hash_rejected() {
        let mut chain = Chain::new();
        let block = make_block(1, "wrong_hash", INITIAL_NONCE);
        assert!(matches!(chain.add_block(block), Err(ChainError::InvalidPrevHash(_))));
    }

    #[test]
    fn test_validate_chain_ok() {
        let mut chain = Chain::new();
        let h = chain.tip().unwrap().hash.clone();
        let b = make_block(1, &h, INITIAL_NONCE);
        chain.add_block(b).unwrap();
        assert!(chain.validate_chain().is_ok());
    }

    #[test]
    fn test_get_block_by_hash() {
        let chain = Chain::new();
        let genesis_hash = chain.blocks[0].hash.clone();
        assert!(chain.get_block_by_hash(&genesis_hash).is_some());
    }
}
