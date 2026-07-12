#!/usr/bin/env python3
"""
AI-Powered Threat Detection System

Detects network anomalies, suspicious transactions, and potential attacks
using machine learning models.
"""

import numpy as np
from typing import Dict, List, Tuple
from enum import Enum
from dataclasses import dataclass


class ThreatLevel(Enum):
    """Security threat levels"""
    NORMAL = 0
    CAUTION = 1
    WARNING = 2
    CRITICAL = 3


@dataclass
class AnomalyScore:
    """Represents an anomaly detection result"""
    score: float  # 0.0 to 1.0
    threat_level: ThreatLevel
    description: str
    recommendations: List[str]


class ThreatDetector:
    """AI-based threat detection system"""
    
    def __init__(self):
        self.baseline_metrics = {}
        self.threat_history = []
        self.model_accuracy = 0.85
    
    def detect_transaction_anomaly(self, transaction: Dict) -> AnomalyScore:
        """Detect anomalies in transaction"""
        from_address = transaction.get('from')
        to_address = transaction.get('to')
        amount = transaction.get('amount', 0)
        
        # Extract features
        features = self._extract_transaction_features(transaction)
        
        # Score anomaly
        score = self._calculate_anomaly_score(features)
        
        # Determine threat level
        if score > 0.8:
            threat_level = ThreatLevel.CRITICAL
            description = "CRITICAL: Highly suspicious transaction detected"
        elif score > 0.6:
            threat_level = ThreatLevel.WARNING
            description = "WARNING: Suspicious transaction pattern detected"
        elif score > 0.4:
            threat_level = ThreatLevel.CAUTION
            description = "CAUTION: Unusual transaction activity"
        else:
            threat_level = ThreatLevel.NORMAL
            description = "Normal transaction"
        
        # Generate recommendations
        recommendations = self._generate_recommendations(threat_level, transaction)
        
        return AnomalyScore(
            score=score,
            threat_level=threat_level,
            description=description,
            recommendations=recommendations
        )
    
    def detect_network_anomaly(self, network_metrics: Dict) -> AnomalyScore:
        """Detect anomalies in network metrics"""
        features = self._extract_network_features(network_metrics)
        score = self._calculate_anomaly_score(features)
        
        if score > 0.7:
            threat_level = ThreatLevel.CRITICAL
            description = "CRITICAL: Severe network anomaly detected"
        elif score > 0.5:
            threat_level = ThreatLevel.WARNING
            description = "WARNING: Network behaving abnormally"
        else:
            threat_level = ThreatLevel.NORMAL
            description = "Network operating normally"
        
        recommendations = self._generate_recommendations(threat_level, network_metrics)
        
        return AnomalyScore(
            score=score,
            threat_level=threat_level,
            description=description,
            recommendations=recommendations
        )
    
    def _extract_transaction_features(self, tx: Dict) -> np.ndarray:
        """Extract features from transaction for ML model"""
        features = []
        
        # Amount anomaly
        amount = tx.get('amount', 0)
        avg_amount = np.mean(list(map(lambda x: x.get('amount', 0), self.threat_history[-100:] or [1])))
        features.append(amount / max(avg_amount, 1))
        
        # Frequency anomaly
        from_address = tx.get('from')
        recent_from_txs = sum(1 for t in self.threat_history[-50:] if t.get('from') == from_address)
        features.append(min(recent_from_txs / 10, 1.0))
        
        # Known address check
        known_addresses = set([t.get('from') for t in self.threat_history])
        features.append(0.0 if from_address in known_addresses else 1.0)
        
        # Recipient is new
        to_address = tx.get('to')
        known_recipients = set([t.get('to') for t in self.threat_history])
        features.append(0.0 if to_address in known_recipients else 0.7)
        
        # Gas limit anomaly
        gas = tx.get('gas_limit', 21000)
        features.append(1.0 if gas > 1000000 else 0.1)
        
        return np.array(features)
    
    def _extract_network_features(self, metrics: Dict) -> np.ndarray:
        """Extract features from network metrics"""
        features = []
        
        # Node participation
        online = metrics.get('online_nodes', 0)
        total = metrics.get('total_nodes', 1)
        features.append(1.0 - (online / max(total, 1)))
        
        # Latency anomaly
        latency = metrics.get('avg_latency_ms', 0)
        features.append(min(latency / 1000, 1.0))  # Normalize to 0-1
        
        # Transaction backlog
        backlog = metrics.get('transaction_backlog', 0)
        features.append(min(backlog / 1000, 1.0))
        
        # Block time anomaly
        block_time = metrics.get('avg_block_time', 10)
        features.append(abs(block_time - 10) / 10)  # Target is 10 seconds
        
        return np.array(features)
    
    def _calculate_anomaly_score(self, features: np.ndarray) -> float:
        """Calculate anomaly score using ML model (simplified)"""
        # Simplified neural network scoring
        # In production, this would use a trained ML model
        
        # Normalize features
        normalized = features / (np.max(np.abs(features)) + 1e-10)
        
        # Simple weighted combination
        weights = np.array([0.3, 0.25, 0.2, 0.15, 0.1])
        score = np.dot(normalized[:len(weights)], weights)
        
        return float(np.clip(score, 0.0, 1.0))
    
    def _generate_recommendations(self, threat_level: ThreatLevel, context: Dict) -> List[str]:
        """Generate security recommendations based on threat level"""
        recommendations = []
        
        if threat_level == ThreatLevel.CRITICAL:
            recommendations = [
                "IMMEDIATE ACTION REQUIRED",
                "Switch to PoW consensus for maximum security",
                "Increase block validation strictness",
                "Notify network administrators immediately",
                "Enable enhanced monitoring"
            ]
        
        elif threat_level == ThreatLevel.WARNING:
            recommendations = [
                "Monitor transaction closely",
                "Consider switching to hybrid consensus",
                "Increase validation checks",
                "Log all related activities"
            ]
        
        elif threat_level == ThreatLevel.CAUTION:
            recommendations = [
                "Continue normal monitoring",
                "Track this pattern",
                "Keep security level elevated"
            ]
        
        return recommendations
    
    def update_baseline(self, metrics: Dict):
        """Update baseline metrics for comparison"""
        for key, value in metrics.items():
            if key not in self.baseline_metrics:
                self.baseline_metrics[key] = []
            self.baseline_metrics[key].append(value)
            
            # Keep only last 1000 samples
            if len(self.baseline_metrics[key]) > 1000:
                self.baseline_metrics[key] = self.baseline_metrics[key][-1000:]
    
    def record_threat(self, threat_data: Dict):
        """Record threat event for learning"""
        self.threat_history.append(threat_data)
        
        # Keep only last 10000 events
        if len(self.threat_history) > 10000:
            self.threat_history = self.threat_history[-10000:]


class AnomalyDetector:
    """Statistical anomaly detection"""
    
    @staticmethod
    def detect_outliers(data: List[float], threshold: float = 2.5) -> List[bool]:
        """Detect outliers using Z-score method"""
        mean = np.mean(data)
        std = np.std(data) + 1e-10
        
        z_scores = [(x - mean) / std for x in data]
        return [abs(z) > threshold for z in z_scores]
    
    @staticmethod
    def detect_sudden_change(data: List[float], threshold: float = 0.5) -> bool:
        """Detect sudden change in metric"""
        if len(data) < 2:
            return False
        
        recent_avg = np.mean(data[-10:])
        older_avg = np.mean(data[:-10]) if len(data) > 10 else data[0]
        
        change = abs(recent_avg - older_avg) / (older_avg + 1e-10)
        return change > threshold


if __name__ == "__main__":
    # Example usage
    detector = ThreatDetector()
    
    # Test transaction anomaly detection
    normal_tx = {
        'from': '0x1234',
        'to': '0x5678',
        'amount': 100,
        'gas_limit': 21000
    }
    
    result = detector.detect_transaction_anomaly(normal_tx)
    print(f"Transaction Threat Level: {result.threat_level}")
    print(f"Anomaly Score: {result.score:.3f}")
    print(f"Description: {result.description}")
    print(f"Recommendations: {result.recommendations}")
