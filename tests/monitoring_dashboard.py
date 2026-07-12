#!/usr/bin/env python3
"""
Monitoring Dashboard

Real-time monitoring of system metrics and performance.
Provides live visualization of threat levels, consensus state, and AI learning.
"""

import time
import json
from typing import Dict, List
from datetime import datetime
from collections import deque


class MonitoringDashboard:
    """Real-time system monitoring dashboard"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.metrics_history = deque(maxlen=max_history)
        self.threat_alerts = deque(maxlen=50)
        self.consensus_history = deque(maxlen=max_history)
        self.performance_metrics = {}
        
        print("\n" + "="*70)
        print("📊 MONITORING DASHBOARD INITIALIZED")
        print("="*70 + "\n")
    
    def record_metrics(self, metrics: Dict):
        """Record system metrics"""
        timestamp = datetime.now()
        
        record = {
            "timestamp": timestamp.isoformat(),
            "threat_level": metrics.get("threat_level", 0),
            "defense_level": metrics.get("defense_level", "NORMAL"),
            "consensus_type": metrics.get("consensus_type", "HYBRID"),
            "network_health": metrics.get("network_health", 0),
            "ai_confidence": metrics.get("ai_confidence", 0),
            "transactions_pending": metrics.get("transactions_pending", 0),
            "blocks_height": metrics.get("blocks_height", 0),
            "cpu_usage": metrics.get("cpu_usage", 0),
            "memory_usage_mb": metrics.get("memory_usage_mb", 0)
        }
        
        self.metrics_history.append(record)
        
        # Check for alerts
        if record["threat_level"] > 0.7:
            self.threat_alerts.append({
                "timestamp": timestamp.isoformat(),
                "level": record["defense_level"],
                "threat_score": record["threat_level"]
            })
    
    def record_consensus_change(self, previous_type: str, new_type: str, reason: str):
        """Record consensus type change"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "previous": previous_type,
            "new": new_type,
            "reason": reason
        }
        
        self.consensus_history.append(record)
    
    def update_performance(self, component: str, metric_name: str, value: float):
        """Update performance metric"""
        if component not in self.performance_metrics:
            self.performance_metrics[component] = {}
        
        self.performance_metrics[component][metric_name] = value
    
    def display_dashboard(self):
        """Display dashboard in terminal"""
        if not self.metrics_history:
            print("No data to display yet")
            return
        
        latest = self.metrics_history[-1]
        
        # Clear screen
        print("\033[2J\033[H")  # ANSI codes to clear terminal
        
        print("\n" + "="*70)
        print("📊 SATOSHI OS - AI BLOCKCHAIN DASHBOARD")
        print(f"Timestamp: {latest['timestamp']}")
        print("="*70 + "\n")
        
        # Threat Level Display
        threat_level = latest["threat_level"]
        threat_bar = self._create_threat_bar(threat_level)
        print(f"🎯 THREAT LEVEL: {threat_bar} {threat_level:.1%}")
        print(f"🛡️  DEFENSE LEVEL: {latest['defense_level']}")
        print()
        
        # Consensus Info
        print(f"⚙️  CONSENSUS: {latest['consensus_type']}")
        print(f"🕸️  NETWORK HEALTH: {latest['network_health']:.1%}")
        print()
        
        # Performance Metrics
        print(f"🧠 AI CONFIDENCE: {latest['ai_confidence']:.1%}")
        print(f"📈 PENDING TX: {latest['transactions_pending']}")
        print(f"🔗 CHAIN HEIGHT: {latest['blocks_height']}")
        print()
        
        # Resource Usage
        cpu_bar = self._create_resource_bar(latest['cpu_usage'])
        mem_bar = self._create_resource_bar(latest['memory_usage_mb'] / 2048)  # Assume 2GB max
        print(f"💻 CPU: {cpu_bar} {latest['cpu_usage']:.1%}")
        print(f"🧬 MEMORY: {mem_bar} {latest['memory_usage_mb']:.0f}MB")
        print()
        
        # Recent Alerts
        if self.threat_alerts:
            print(f"⚠️  RECENT ALERTS ({len(self.threat_alerts)}):")
            for alert in list(self.threat_alerts)[-5:]:
                print(f"   - {alert['timestamp']}: {alert['level']} ({alert['threat_score']:.1%})")
        else:
            print("✅ NO RECENT ALERTS")
        
        print()
        
        # Consensus Changes
        if self.consensus_history:
            print(f"🔄 RECENT CONSENSUS CHANGES ({len(self.consensus_history)}):")
            for change in list(self.consensus_history)[-3:]:
                print(f"   - {change['timestamp']}: {change['previous']} → {change['new']}")
        
        print("\n" + "="*70 + "\n")
    
    def display_history_graph(self, metric_name: str = "threat_level"):
        """Display historical graph of metric"""
        if not self.metrics_history:
            print("No history data")
            return
        
        values = [m[metric_name] for m in self.metrics_history]
        
        # Normalize values for display
        if max(values) > 0:
            normalized = [int((v / max(values)) * 20) for v in values]
        else:
            normalized = [0] * len(values)
        
        print(f"\n📈 {metric_name.upper()} TREND:")
        print("-" * 70)
        
        for val in normalized:
            bar = "█" * val + "░" * (20 - val)
            print(f"|{bar}|")
        
        print("-" * 70)
        print(f"Min: {min(values):.3f}, Max: {max(values):.3f}, Avg: {sum(values)/len(values):.3f}")
    
    def _create_threat_bar(self, threat_level: float) -> str:
        """Create visual threat level bar"""
        filled = int(threat_level * 10)
        bar = "🔴" * filled + "🟢" * (10 - filled)
        return bar
    
    def _create_resource_bar(self, usage: float) -> str:
        """Create visual resource usage bar"""
        filled = int(usage * 20)
        return "█" * filled + "░" * (20 - filled)
    
    def export_metrics(self, filename: str = "metrics_export.json"):
        """Export metrics to JSON file"""
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": list(self.metrics_history),
            "alerts": list(self.threat_alerts),
            "consensus_changes": list(self.consensus_history),
            "performance": self.performance_metrics
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Metrics exported to {filename}")
    
    def get_summary(self) -> Dict:
        """Get summary of all metrics"""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        threat_levels = [m["threat_level"] for m in self.metrics_history]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_status": {
                "threat_level": latest["threat_level"],
                "defense_level": latest["defense_level"],
                "consensus_type": latest["consensus_type"],
                "network_health": latest["network_health"]
            },
            "statistics": {
                "avg_threat_level": sum(threat_levels) / len(threat_levels),
                "max_threat_level": max(threat_levels),
                "min_threat_level": min(threat_levels),
                "alert_count": len(self.threat_alerts),
                "consensus_changes": len(self.consensus_history)
            }
        }


if __name__ == "__main__":
    # Example usage
    dashboard = MonitoringDashboard()
    
    # Simulate metrics
    print("Simulating dashboard updates...\n")
    
    import numpy as np
    
    for i in range(10):
        metrics = {
            "threat_level": np.random.uniform(0, 1),
            "defense_level": ["NORMAL", "CAUTION", "WARNING", "CRITICAL"][int(np.random.uniform(0, 4))],
            "consensus_type": ["POW", "POS", "HYBRID_50_50", "HYBRID_70_30"][int(np.random.uniform(0, 4))],
            "network_health": np.random.uniform(0.3, 1.0),
            "ai_confidence": np.random.uniform(0.7, 0.99),
            "transactions_pending": int(np.random.uniform(100, 5000)),
            "blocks_height": 1000 + i * 10,
            "cpu_usage": np.random.uniform(0.1, 0.8),
            "memory_usage_mb": np.random.uniform(500, 1500)
        }
        
        dashboard.record_metrics(metrics)
        
        time.sleep(0.1)
    
    # Display dashboard
    dashboard.display_dashboard()
    
    # Show history
    dashboard.display_history_graph("threat_level")
    
    # Get summary
    print("\nDashboard Summary:")
    summary = dashboard.get_summary()
    print(json.dumps(summary, indent=2))
    
    # Export
    dashboard.export_metrics()
