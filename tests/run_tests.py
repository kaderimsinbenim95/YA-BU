#!/usr/bin/env python3
"""
Simulation Runner

Launches and manages all tests and simulations.
Provides easy interface for running comprehensive test suite.
"""

import sys
import os
import time
import argparse
from datetime import datetime

# Ensure the project root is on sys.path so both `python tests/run_tests.py`
# and `python -m tests.run_tests` work correctly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Import test modules (use relative imports when run as a package)
from tests.test_simulation import SimulationTestSuite
from tests.threat_scenarios import ThreatScenarioSimulator
from tests.performance_benchmark import PerformanceBenchmark
from tests.monitoring_dashboard import MonitoringDashboard


class SimulationRunner:
    """Main simulation runner orchestrator"""
    
    def __init__(self):
        self.start_time = time.time()
        self.results = {}
        
        print("\n" + "="*70)
        print("🚀 SATOSHI OS - AI BLOCKCHAIN SIMULATION RUNNER")
        print(f"Started: {datetime.now()}")
        print("="*70 + "\n")
    
    def run_full_simulation(self, verbose: bool = True):
        """Run complete simulation suite"""
        print("RUNNING FULL SIMULATION SUITE\n")
        
        # 1. Component Tests
        if verbose:
            print("\n[1/4] Running component tests...\n")
        suite = SimulationTestSuite("Full Simulation Run")
        suite.run_all_tests()
        self.results['component_tests'] = suite.results
        
        # 2. Threat Scenarios
        if verbose:
            print("\n[2/4] Running threat scenarios...\n")
        threat_sim = ThreatScenarioSimulator()
        threat_sim.run_all_scenarios()
        self.results['threat_scenarios'] = threat_sim.scenario_results
        
        # 3. Performance Benchmarks
        if verbose:
            print("\n[3/4] Running performance benchmarks...\n")
        benchmark = PerformanceBenchmark()
        benchmark.run_all_benchmarks()
        self.results['performance'] = benchmark.results
        
        # 4. Dashboard Demo
        if verbose:
            print("\n[4/4] Initializing monitoring dashboard...\n")
        dashboard = MonitoringDashboard()
        
        # Simulate some metrics for dashboard
        import numpy as np
        for i in range(20):
            metrics = {
                "threat_level": np.sin(i/5) * 0.5 + 0.3,
                "defense_level": "NORMAL" if i % 5 != 0 else "CAUTION",
                "consensus_type": "HYBRID_50_50",
                "network_health": 0.85,
                "ai_confidence": 0.92,
                "transactions_pending": int(1000 + i*100),
                "blocks_height": 1000 + i*10,
                "cpu_usage": np.random.uniform(0.2, 0.6),
                "memory_usage_mb": np.random.uniform(800, 1200)
            }
            dashboard.record_metrics(metrics)
        
        dashboard.display_dashboard()
        self.results['dashboard'] = dashboard.get_summary()
        
        # Print final summary
        self.print_summary()
    
    def run_quick_test(self):
        """Run quick test suite (component tests only)"""
        print("RUNNING QUICK TEST SUITE\n")
        
        suite = SimulationTestSuite("Quick Test")
        suite.run_all_tests()
        
        self.print_summary()
    
    def run_threat_simulation(self):
        """Run threat scenario simulation only"""
        print("RUNNING THREAT SCENARIO SIMULATION\n")
        
        threat_sim = ThreatScenarioSimulator()
        threat_sim.run_all_scenarios()
        
        self.print_summary()
    
    def run_benchmark(self):
        """Run performance benchmarks only"""
        print("RUNNING PERFORMANCE BENCHMARKS\n")
        
        benchmark = PerformanceBenchmark()
        benchmark.run_all_benchmarks()
        
        self.print_summary()
    
    def print_summary(self):
        """Print final summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*70)
        print("✅ SIMULATION COMPLETE")
        print("="*70)
        print(f"\nTotal Time: {elapsed:.2f} seconds")
        print(f"Completed: {datetime.now()}")
        print("\n" + "="*70 + "\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="SatoshiOS-AI-Blockchain Simulation Runner"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "quick", "threat", "benchmark"],
        default="full",
        help="Test mode to run"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    runner = SimulationRunner()
    
    if args.mode == "full":
        runner.run_full_simulation(verbose=args.verbose)
    elif args.mode == "quick":
        runner.run_quick_test()
    elif args.mode == "threat":
        runner.run_threat_simulation()
    elif args.mode == "benchmark":
        runner.run_benchmark()


if __name__ == "__main__":
    main()
