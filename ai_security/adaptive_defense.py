#!/usr/bin/env python3
"""
Adaptive Defense System

Automatically adjusts security parameters, consensus type, and defense mechanisms
based on threat level and network conditions.
"""

import time
from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass


class DefenseLevel(Enum):
    """System defense levels"""
    NORMAL = 0          # Level 0: Normal operations
    CAUTION = 1         # Level 1: Increased monitoring
    WARNING = 2         # Level 2: Enhanced verification
    CRITICAL = 3        # Level 3: Emergency mode


class ConsensusMode(Enum):
    """Available consensus modes"""
    POW_ONLY = "pow_only"              # Proof of Work only
    POS_ONLY = "pos_only"              # Proof of Stake only
    HYBRID_50_50 = "hybrid_50_50"      # 50/50 PoW+PoS
    HYBRID_70_30 = "hybrid_70_30"      # 70% PoS + 30% PoW
    HYBRID_30_70 = "hybrid_30_70"      # 30% PoS + 70% PoW


@dataclass
class DefenseStrategy:
    """Represents a defense strategy"""
    level: DefenseLevel
    consensus_mode: ConsensusMode
    block_validation_strictness: float  # 0.0-1.0
    transaction_throughput: int          # max TPS
    ai_monitoring_intensity: float       # 0.0-1.0
    network_timeout_ms: int
    slashing_penalty_percent: int        # For PoS
    pow_difficulty_multiplier: float
    max_pending_transactions: int
    require_additional_verification: bool


class AdaptiveDefenseSystem:
    """Dynamically adjusts defense based on threats"""
    
    def __init__(self):
        self.current_defense_level = DefenseLevel.NORMAL
        self.current_consensus_mode = ConsensusMode.HYBRID_50_50

        # Threat tracking
        self.threat_score = 0.0  # 0.0-1.0
        self.recent_attacks: List[Dict] = []
        self.threat_history: List[float] = []

        # Configuration
        self.auto_adapt_enabled = True
        self.adaptation_cooldown = 60  # seconds between adaptations
        self.last_adaptation_time = 0

        # Defense effectiveness tracking
        self.defense_effectiveness = {
            "blocked_attacks": 0,
            "false_positives": 0,
            "response_time_ms": 0,
            "total_defense_activations": 0
        }

        # Strategies for each level (must be defined before _get_strategy is called)
        self.strategies = {
            DefenseLevel.NORMAL: DefenseStrategy(
                level=DefenseLevel.NORMAL,
                consensus_mode=ConsensusMode.HYBRID_50_50,
                block_validation_strictness=0.5,
                transaction_throughput=1000,
                ai_monitoring_intensity=0.3,
                network_timeout_ms=5000,
                slashing_penalty_percent=10,
                pow_difficulty_multiplier=1.0,
                max_pending_transactions=5000,
                require_additional_verification=False
            ),
            DefenseLevel.CAUTION: DefenseStrategy(
                level=DefenseLevel.CAUTION,
                consensus_mode=ConsensusMode.HYBRID_70_30,
                block_validation_strictness=0.7,
                transaction_throughput=500,
                ai_monitoring_intensity=0.6,
                network_timeout_ms=3000,
                slashing_penalty_percent=15,
                pow_difficulty_multiplier=1.5,
                max_pending_transactions=2000,
                require_additional_verification=False
            ),
            DefenseLevel.WARNING: DefenseStrategy(
                level=DefenseLevel.WARNING,
                consensus_mode=ConsensusMode.HYBRID_30_70,
                block_validation_strictness=0.85,
                transaction_throughput=250,
                ai_monitoring_intensity=0.8,
                network_timeout_ms=2000,
                slashing_penalty_percent=20,
                pow_difficulty_multiplier=2.0,
                max_pending_transactions=1000,
                require_additional_verification=True
            ),
            DefenseLevel.CRITICAL: DefenseStrategy(
                level=DefenseLevel.CRITICAL,
                consensus_mode=ConsensusMode.POW_ONLY,
                block_validation_strictness=0.95,
                transaction_throughput=100,
                ai_monitoring_intensity=1.0,
                network_timeout_ms=1000,
                slashing_penalty_percent=30,
                pow_difficulty_multiplier=3.0,
                max_pending_transactions=100,
                require_additional_verification=True
            )
        }

        # Set initial strategy now that self.strategies is available
        self.current_strategy = self._get_strategy(DefenseLevel.NORMAL)

    def update_threat_level(self, threat_score: float, attack_info: Optional[Dict] = None):
        """Update threat level and adapt defenses"""
        self.threat_score = max(0.0, min(1.0, threat_score))
        self.threat_history.append(self.threat_score)
        
        # Keep last 100 threat scores
        if len(self.threat_history) > 100:
            self.threat_history = self.threat_history[-100:]
        
        # Record attack if detected
        if attack_info:
            self.recent_attacks.append({
                "timestamp": time.time(),
                "info": attack_info,
                "threat_score": threat_score
            })
            # Keep last 50 attacks
            if len(self.recent_attacks) > 50:
                self.recent_attacks = self.recent_attacks[-50:]
        
        # Auto-adapt if enabled
        if self.auto_adapt_enabled:
            self._check_and_adapt()
    
    def _check_and_adapt(self):
        """Check threat level and adapt defenses"""
        current_time = time.time()
        
        # Cooldown check
        if current_time - self.last_adaptation_time < self.adaptation_cooldown:
            return
        
        # Determine new defense level
        new_level = self._determine_defense_level()
        
        # Adapt if changed
        if new_level != self.current_defense_level:
            self._apply_defense_strategy(new_level)
            self.last_adaptation_time = current_time
    
    def _determine_defense_level(self) -> DefenseLevel:
        """Determine appropriate defense level based on threat score"""
        # Calculate threat trend
        if len(self.threat_history) > 1:
            trend = (self.threat_history[-1] - self.threat_history[-10]) if len(self.threat_history) >= 10 else 0
        else:
            trend = 0
        
        # Weight recent scores more heavily
        recent_avg = sum(self.threat_history[-10:]) / min(10, len(self.threat_history)) if self.threat_history else 0
        
        # Determine level
        if self.threat_score >= 0.8 or recent_avg >= 0.75:
            return DefenseLevel.CRITICAL
        elif self.threat_score >= 0.6 or recent_avg >= 0.5:
            return DefenseLevel.WARNING
        elif self.threat_score >= 0.4 or recent_avg >= 0.3:
            return DefenseLevel.CAUTION
        else:
            return DefenseLevel.NORMAL
    
    def _apply_defense_strategy(self, level: DefenseLevel):
        """Apply defense strategy for given level"""
        strategy = self.strategies[level]
        
        self.current_defense_level = level
        self.current_strategy = strategy
        self.current_consensus_mode = strategy.consensus_mode
        
        self.defense_effectiveness["total_defense_activations"] += 1
        
        print(f"\n{'='*60}")
        print(f"[Defense] ⚠️  DEFENSE LEVEL CHANGED")
        print(f"{'='*60}")
        print(f"New Level: {level.name}")
        print(f"Threat Score: {self.threat_score:.2f}")
        print(f"\nApplied Strategy:")
        print(f"  • Consensus Mode: {strategy.consensus_mode.value}")
        print(f"  • Block Validation Strictness: {strategy.block_validation_strictness:.0%}")
        print(f"  • Max Throughput: {strategy.transaction_throughput} TPS")
        print(f"  • AI Monitoring Intensity: {strategy.ai_monitoring_intensity:.0%}")
        print(f"  • Network Timeout: {strategy.network_timeout_ms}ms")
        print(f"  • Slashing Penalty: {strategy.slashing_penalty_percent}%")
        print(f"  • PoW Difficulty: x{strategy.pow_difficulty_multiplier}")
        print(f"  • Additional Verification: {strategy.require_additional_verification}")
        print(f"{'='*60}\n")
    
    def _get_strategy(self, level: DefenseLevel) -> DefenseStrategy:
        """Get strategy for defense level"""
        return self.strategies[level]
    
    def should_accept_transaction(self, transaction: Dict) -> bool:
        """Determine if transaction should be accepted"""
        strategy = self.current_strategy
        
        # Critical: reject most transactions
        if self.current_defense_level == DefenseLevel.CRITICAL:
            # Only accept high-priority transactions
            return transaction.get("priority", 0) >= 9
        
        # Warning: reject suspicious transactions
        elif self.current_defense_level == DefenseLevel.WARNING:
            # Check transaction score
            tx_score = transaction.get("anomaly_score", 0.0)
            return tx_score < 0.6
        
        # Caution: require higher confidence
        elif self.current_defense_level == DefenseLevel.CAUTION:
            tx_score = transaction.get("anomaly_score", 0.0)
            return tx_score < 0.4
        
        # Normal: accept all
        else:
            return True
    
    def should_validate_block(self, block: Dict) -> bool:
        """Determine if block should be validated"""
        strategy = self.current_strategy
        
        # Use strictness to determine validation requirements
        if strategy.require_additional_verification:
            return True
        
        return True
    
    def get_consensus_parameters(self) -> Dict:
        """Get consensus parameters for current strategy"""
        return {
            "mode": self.current_consensus_mode.value,
            "pow_difficulty_multiplier": self.current_strategy.pow_difficulty_multiplier,
            "pos_slashing_percent": self.current_strategy.slashing_penalty_percent,
            "require_higher_validation": self.current_strategy.require_additional_verification
        }
    
    def get_threat_analysis(self) -> Dict:
        """Get detailed threat analysis"""
        if len(self.threat_history) < 2:
            trend = "unknown"
        else:
            trend_value = self.threat_history[-1] - self.threat_history[-2]
            if trend_value > 0.1:
                trend = "increasing"
            elif trend_value < -0.1:
                trend = "decreasing"
            else:
                trend = "stable"
        
        return {
            "current_threat_score": self.threat_score,
            "defense_level": self.current_defense_level.name,
            "trend": trend,
            "recent_attacks": len(self.recent_attacks),
            "avg_threat_score": sum(self.threat_history) / len(self.threat_history) if self.threat_history else 0,
            "defense_effectiveness": self.defense_effectiveness
        }
    
    def reset_to_normal(self):
        """Manually reset to normal defense level"""
        print("[Defense] Resetting to NORMAL defense level")
        self.threat_score = 0.0
        self._apply_defense_strategy(DefenseLevel.NORMAL)
    
    def set_auto_adaptation(self, enabled: bool):
        """Enable/disable automatic adaptation"""
        self.auto_adapt_enabled = enabled
        print(f"[Defense] Auto-adaptation: {'ENABLED' if enabled else 'DISABLED'}")
    
    def get_defense_status(self) -> Dict:
        """Get current defense status"""
        return {
            "current_level": self.current_defense_level.name,
            "threat_score": self.threat_score,
            "consensus_mode": self.current_consensus_mode.value,
            "auto_adaptation_enabled": self.auto_adapt_enabled,
            "last_adaptation_time": self.last_adaptation_time,
            "recent_attacks": len(self.recent_attacks),
            "strategy": {
                "validation_strictness": self.current_strategy.block_validation_strictness,
                "max_throughput_tps": self.current_strategy.transaction_throughput,
                "ai_monitoring_intensity": self.current_strategy.ai_monitoring_intensity,
                "pow_difficulty_multiplier": self.current_strategy.pow_difficulty_multiplier
            }
        }


if __name__ == "__main__":
    # Example usage
    defense = AdaptiveDefenseSystem()
    
    print("\n[Demo] Testing Adaptive Defense System\n")
    
    # Simulate normal conditions
    print("1. Normal conditions:")
    defense.update_threat_level(0.1)
    print(defense.get_defense_status())
    time.sleep(2)
    
    # Simulate caution level
    print("\n2. Caution conditions:")
    defense.update_threat_level(0.4, {"type": "unusual_activity"})
    time.sleep(2)
    
    # Simulate warning level
    print("\n3. Warning conditions:")
    defense.update_threat_level(0.65, {"type": "potential_attack"})
    time.sleep(2)
    
    # Simulate critical level
    print("\n4. Critical conditions:")
    defense.update_threat_level(0.9, {"type": "active_attack"})
    time.sleep(2)
    
    # Get analysis
    print("\n5. Threat Analysis:")
    import json
    analysis = defense.get_threat_analysis()
    print(json.dumps(analysis, indent=2))
