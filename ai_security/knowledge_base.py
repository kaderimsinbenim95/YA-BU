#!/usr/bin/env python3
"""
Knowledge Base System

Stores and retrieves threat patterns, attack signatures, and learned models
for continuous reference and improvement.
"""

import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum


class KnowledgeType(Enum):
    """Types of knowledge to store"""
    THREAT_PATTERN = "threat_pattern"
    ATTACK_SIGNATURE = "attack_signature"
    DEFENSE_STRATEGY = "defense_strategy"
    MODEL_CHECKPOINT = "model_checkpoint"
    NETWORK_BASELINE = "network_baseline"
    VULNERABILITY = "vulnerability"


@dataclass
class KnowledgeEntry:
    """Single knowledge base entry"""
    knowledge_type: KnowledgeType
    key: str
    data: Dict[str, Any]
    confidence: float  # 0.0-1.0
    created_at: float
    updated_at: float
    hits: int  # Number of times referenced
    effectiveness: float  # How well this knowledge helped


class KnowledgeBase:
    """Persistent knowledge storage and retrieval"""
    
    def __init__(self, db_path: str = "satoshi_knowledge.db"):
        self.db_path = db_path
        self.cache: Dict[str, KnowledgeEntry] = {}
        self.max_cache_size = 1000
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                key TEXT PRIMARY KEY,
                knowledge_type TEXT NOT NULL,
                data TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                hits INTEGER NOT NULL,
                effectiveness REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threat_patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_name TEXT NOT NULL,
                features TEXT NOT NULL,
                threat_level INTEGER NOT NULL,
                frequency INTEGER NOT NULL,
                last_seen REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attack_signatures (
                signature_id TEXT PRIMARY KEY,
                attack_type TEXT NOT NULL,
                signature_data TEXT NOT NULL,
                severity INTEGER NOT NULL,
                detection_method TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def store_threat_pattern(self, pattern_name: str, features: List[float], 
                            threat_level: int, confidence: float = 0.8) -> str:
        """Store identified threat pattern"""
        pattern_id = f"pattern_{hash(pattern_name)}_{int(datetime.now().timestamp())}"
        
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.THREAT_PATTERN,
            key=pattern_id,
            data={
                "pattern_name": pattern_name,
                "features": features,
                "threat_level": threat_level
            },
            confidence=confidence,
            created_at=datetime.now().timestamp(),
            updated_at=datetime.now().timestamp(),
            hits=0,
            effectiveness=0.0
        )
        
        self._store_entry(entry)
        print(f"[KB] Stored threat pattern: {pattern_name} (Confidence: {confidence:.2%})")
        return pattern_id
    
    def store_attack_signature(self, attack_type: str, signature_data: Dict,
                              severity: int, detection_method: str) -> str:
        """Store attack signature for detection"""
        sig_id = f"sig_{hash(attack_type)}_{int(datetime.now().timestamp())}"
        
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.ATTACK_SIGNATURE,
            key=sig_id,
            data={
                "attack_type": attack_type,
                "signature_data": signature_data,
                "detection_method": detection_method
            },
            confidence=0.9,
            created_at=datetime.now().timestamp(),
            updated_at=datetime.now().timestamp(),
            hits=0,
            effectiveness=0.0
        )
        
        self._store_entry(entry)
        print(f"[KB] Stored attack signature: {attack_type} (Severity: {severity})")
        return sig_id
    
    def store_defense_strategy(self, strategy_name: str, parameters: Dict,
                              effectiveness: float) -> str:
        """Store effective defense strategy"""
        strategy_id = f"strategy_{hash(strategy_name)}_{int(datetime.now().timestamp())}"
        
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.DEFENSE_STRATEGY,
            key=strategy_id,
            data={
                "strategy_name": strategy_name,
                "parameters": parameters
            },
            confidence=effectiveness,
            created_at=datetime.now().timestamp(),
            updated_at=datetime.now().timestamp(),
            hits=1,
            effectiveness=effectiveness
        )
        
        self._store_entry(entry)
        print(f"[KB] Stored defense strategy: {strategy_name} (Effectiveness: {effectiveness:.2%})")
        return strategy_id
    
    def store_model_checkpoint(self, model_version: int, model_data: Dict,
                              accuracy: float) -> str:
        """Store trained model checkpoint"""
        checkpoint_id = f"model_v{model_version}_{int(datetime.now().timestamp())}"
        
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.MODEL_CHECKPOINT,
            key=checkpoint_id,
            data={
                "model_version": model_version,
                "model_data": model_data,
                "accuracy": accuracy
            },
            confidence=accuracy,
            created_at=datetime.now().timestamp(),
            updated_at=datetime.now().timestamp(),
            hits=0,
            effectiveness=accuracy
        )
        
        self._store_entry(entry)
        print(f"[KB] Stored model checkpoint: v{model_version} (Accuracy: {accuracy:.2%})")
        return checkpoint_id
    
    def store_network_baseline(self, metrics: Dict) -> str:
        """Store network baseline for anomaly detection"""
        baseline_id = f"baseline_{int(datetime.now().timestamp())}"
        
        entry = KnowledgeEntry(
            knowledge_type=KnowledgeType.NETWORK_BASELINE,
            key=baseline_id,
            data=metrics,
            confidence=0.8,
            created_at=datetime.now().timestamp(),
            updated_at=datetime.now().timestamp(),
            hits=0,
            effectiveness=0.0
        )
        
        self._store_entry(entry)
        print(f"[KB] Stored network baseline")
        return baseline_id
    
    def retrieve_threat_patterns(self, threat_level: Optional[int] = None) -> List[Dict]:
        """Retrieve threat patterns"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if threat_level is not None:
            cursor.execute("""
                SELECT * FROM knowledge_entries 
                WHERE knowledge_type = ? AND data LIKE ?
                ORDER BY hits DESC
            """, (KnowledgeType.THREAT_PATTERN.value, f'%"threat_level": {threat_level}%'))
        else:
            cursor.execute("""
                SELECT * FROM knowledge_entries 
                WHERE knowledge_type = ?
                ORDER BY hits DESC
            """, (KnowledgeType.THREAT_PATTERN.value,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(row) for row in results]
    
    def retrieve_attack_signatures(self, attack_type: Optional[str] = None) -> List[Dict]:
        """Retrieve attack signatures"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if attack_type:
            cursor.execute("""
                SELECT * FROM knowledge_entries 
                WHERE knowledge_type = ? AND data LIKE ?
                ORDER BY effectiveness DESC
            """, (KnowledgeType.ATTACK_SIGNATURE.value, f'%{attack_type}%'))
        else:
            cursor.execute("""
                SELECT * FROM knowledge_entries 
                WHERE knowledge_type = ?
                ORDER BY effectiveness DESC
            """, (KnowledgeType.ATTACK_SIGNATURE.value,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(row) for row in results]
    
    def retrieve_defense_strategies(self) -> List[Dict]:
        """Retrieve defense strategies sorted by effectiveness"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM knowledge_entries 
            WHERE knowledge_type = ?
            ORDER BY effectiveness DESC
        """, (KnowledgeType.DEFENSE_STRATEGY.value,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(row) for row in results]
    
    def retrieve_latest_model(self) -> Optional[Dict]:
        """Retrieve latest model checkpoint"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM knowledge_entries 
            WHERE knowledge_type = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (KnowledgeType.MODEL_CHECKPOINT.value,))
        
        result = cursor.fetchone()
        conn.close()
        
        return self._row_to_dict(result) if result else None
    
    def increment_usage(self, key: str):
        """Increment hit counter for knowledge entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE knowledge_entries SET hits = hits + 1 WHERE key = ?
        """, (key,))
        
        conn.commit()
        conn.close()
    
    def update_effectiveness(self, key: str, effectiveness: float):
        """Update effectiveness score of knowledge entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE knowledge_entries 
            SET effectiveness = ?, updated_at = ?
            WHERE key = ?
        """, (effectiveness, datetime.now().timestamp(), key))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict:
        """Get knowledge base statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        for k_type in KnowledgeType:
            cursor.execute(
                "SELECT COUNT(*) FROM knowledge_entries WHERE knowledge_type = ?",
                (k_type.value,)
            )
            count = cursor.fetchone()[0]
            stats[k_type.value] = count
        
        cursor.execute("SELECT COUNT(*) FROM knowledge_entries")
        total = cursor.fetchone()[0]
        stats["total_entries"] = total
        
        conn.close()
        return stats
    
    def _store_entry(self, entry: KnowledgeEntry):
        """Store entry in database and cache"""
        # Update cache
        self.cache[entry.key] = entry
        if len(self.cache) > self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self.cache, key=lambda k: self.cache[k].created_at)
            del self.cache[oldest_key]
        
        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO knowledge_entries 
            (key, knowledge_type, data, confidence, created_at, updated_at, hits, effectiveness)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.key,
            entry.knowledge_type.value,
            json.dumps(entry.data),
            entry.confidence,
            entry.created_at,
            entry.updated_at,
            entry.hits,
            entry.effectiveness
        ))
        
        conn.commit()
        conn.close()
    
    def _row_to_dict(self, row: tuple) -> Dict:
        """Convert database row to dictionary"""
        if not row:
            return {}
        
        return {
            "key": row[0],
            "knowledge_type": row[1],
            "data": json.loads(row[2]),
            "confidence": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "hits": row[6],
            "effectiveness": row[7]
        }


if __name__ == "__main__":
    # Example usage
    kb = KnowledgeBase()
    
    print("\n[Demo] Testing Knowledge Base System\n")
    
    # Store threat pattern
    kb.store_threat_pattern(
        "Rapid transactions",
        [0.8, 0.6, 0.7, 0.9],
        threat_level=2,
        confidence=0.85
    )
    
    # Store attack signature
    kb.store_attack_signature(
        "51% Attack",
        {"hash_rate_spike": 200, "consensus_agreement": 0.45},
        severity=3,
        detection_method="hash_rate_monitoring"
    )
    
    # Store defense strategy
    kb.store_defense_strategy(
        "Hybrid consensus switch",
        {"from": "PoS", "to": "PoW", "difficulty_multiplier": 2.0},
        effectiveness=0.92
    )
    
    # Store model checkpoint
    kb.store_model_checkpoint(
        1,
        {"layers": 3, "neurons": [90, 64, 32, 4]},
        accuracy=0.94
    )
    
    # Retrieve and display
    print("\nRetrieving threat patterns:")
    patterns = kb.retrieve_threat_patterns()
    print(json.dumps(patterns, indent=2, default=str))
    
    print("\nKnowledge Base Statistics:")
    stats = kb.get_statistics()
    print(json.dumps(stats, indent=2))
