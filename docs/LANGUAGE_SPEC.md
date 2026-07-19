# 📝 SatoshiLang Language Specification v2.0

## Changelog v2.0
- Full binary operator precedence (`||`, `&&`, comparison, arithmetic)
- Unary operators (`!`, `-`)
- Function call expressions with arguments
- `while` loops
- Field access (`object.field`)
- `float` literal support
- Boolean literals (`true`, `false`) as proper expressions
- VM integration: all constructs compile to SatoshiVM bytecode

---

## 1. Language Overview

**SatoshiLang (.sl)** - Karmaşık sistem mimarisi için tasarlanmış, blockchain-native ve AI-integrated bir programlama dilidir.

### Design Philosophy
- Simple yet powerful
- Blockchain operations as first-class citizens
- Concurrent by default
- AI-friendly syntax
- Type-safe but flexible

---

## 2. Data Types

### 2.1 Primitive Types

```satoshi
// Integers
u8, u16, u32, u64, u128
i8, i16, i32, i64, i128

// Floating Point
f32, f64

// Boolean
bool

// String
str, String

// Address (Special for blockchain)
Address

// Hash (256-bit)
Hash256
```

### 2.2 Special Types

```satoshi
Block {
    index: u64,
    timestamp: u64,
    transactions: Vec<Transaction>,
    nonce: u64,
    hash: Hash256,
    prev_hash: Hash256
}

Transaction {
    from: Address,
    to: Address,
    amount: u64,
    nonce: u32,
    signature: Bytes,
    gas_limit: u64
}
```

---

## 3. Functions

```satoshi
fn add(a: u32, b: u32) -> u32 {
    a + b
}

@ai_monitored
@threat_detection
fn transfer(from: Address, to: Address, amount: u64) {
    validate_signature(from);
    update_ledger(from, to, amount);
}

async task mine_block(block: Block) {
    concurrent {
        verify_pow(&block);
        validate_transactions(&block);
        update_chain(&block);
    }
}
```

---

## 4. Control Flow

```satoshi
if balance > 100 {
    transfer(to, 50);
} else {
    println!("Insufficient balance");
}

match consensus_type {
    PoW => { mine_block(); },
    PoS => { validate_block(); },
    Hybrid => { hybrid_consensus(); }
}

for i in 0..10 {
    println!(i);
}
```

---

## 5. Keywords & Decorators

```
// Control Flow
if else match while for loop break continue return

// Blockchain Specific
contract transaction block chain state ledger verify

// Async/Concurrency
async await concurrent parallel task

// AI/Security
@ai_monitored @threat_detection @anomaly @secure @contract
```

---

**Version**: 1.0  
**Status**: Active Development