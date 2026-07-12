#!/usr/bin/env python3
"""
Performance Benchmark Suite

Measures system performance under various loads including:
- Transaction throughput
- Block mining time
- Consensus latency
- Memory usage
- CPU efficiency
"""

import time
import psutil
import numpy as np
from typing import Dict, List
from datetime import datetime

from core.consensus.hybrid_consensus import HybridConsensus, NetworkMetrics
from ai_security.threat_detection import ThreatDetector
from ai_security.self_learning_engine import SelfLearningEngine


class PerformanceBenchmark:
    """Performance benchmarking suite"""
    
    def __init__(self):
        self.results = {}
        self.consensus = HybridConsensus()
        self.threat_detector = ThreatDetector()
        self.learning_engine = SelfLearningEngine()
        
        print("\n" + "="*70)
        print("⚡ PERFORMANCE BENCHMARK SUITE")
        print("="*70 + "\n")
    
    def run_all_benchmarks(self):
        """Run all benchmarks"""
        print("Starting comprehensive performance benchmarks...\n")
        
        self.benchmark_transaction_throughput()
        self.benchmark_block_mining()
        self.benchmark_threat_detection()
        self.benchmark_consensus_latency()
        self.benchmark_memory_usage()
        self.benchmark_learning_performance()
        
        self.print_benchmark_summary()
    
    def benchmark_transaction_throughput(self):
        """Benchmark 1: Transaction Throughput"""
        print("-" * 70)
        print("BENCHMARK 1: TRANSACTION THROUGHPUT")
        print("-" * 70 + "\n")
        
        transactions_per_second = []
        batch_sizes = [100, 500, 1000, 5000]
        
        for batch_size in batch_sizes:
            start = time.time()
            
            for i in range(batch_size):
                tx = {
                    'from': f'0x{i:04x}',
                    'to': f'0x{i+1:04x}',
                    'amount': np.random.randint(1, 1000),
                    'gas_limit': 21000
                }
                # Simulate processing
                _ = self.threat_detector.detect_transaction_anomaly(tx)
            
            elapsed = time.time() - start
            tps = batch_size / elapsed
            transactions_per_second.append(tps)
            
            print(f"Batch size: {batch_size:5d} | TPS: {tps:8.1f} | Time: {elapsed:6.3f}s")
        
        avg_tps = np.mean(transactions_per_second)
        print(f"\nAverage TPS: {avg_tps:.1f}")
        
        self.results['transaction_throughput'] = {
            'average_tps': avg_tps,
            'tps_per_batch': dict(zip(batch_sizes, transactions_per_second))
        }
        
        print()
    
    def benchmark_block_mining(self):
        """Benchmark 2: Block Mining Performance"""
        print("-" * 70)
        print("BENCHMARK 2: BLOCK MINING PERFORMANCE")
        print("-" * 70 + "\n")
        
        mining_times = []
        block_count = 5
        
        print(f"Mining {block_count} blocks...\n")
        
        for i in range(block_count):
            block = self.consensus.create_block([f"tx_{j}" for j in range(10)])
            
            start = time.time()
            success = self.consensus.mine_block(block)
            mining_time = time.time() - start
            
            mining_times.append(mining_time)
            
            print(f"Block {i+1}: {mining_time:.3f}s - {'✅' if success else '❌'}")
        
        avg_mining_time = np.mean(mining_times)
        print(f"\nAverage mining time: {avg_mining_time:.3f}s")
        
        self.results['block_mining'] = {
            'average_time_seconds': avg_mining_time,
            'mining_times': mining_times
        }
        
        print()
    
    def benchmark_threat_detection(self):
        """Benchmark 3: Threat Detection Latency"""
        print("-" * 70)
        print("BENCHMARK 3: THREAT DETECTION LATENCY")
        print("-" * 70 + "\n")
        
        detection_times = []
        detection_count = 1000
        
        print(f"Running {detection_count} threat detections...\n")
        
        start_total = time.time()
        
        for i in range(detection_count):
            tx = {
                'from': f'0x{np.random.randint(0, 10000):04x}',
                'to': f'0x{np.random.randint(0, 10000):04x}',
                'amount': np.random.randint(1, 10000),
                'gas_limit': 21000
            }
            
            start = time.time()
            _ = self.threat_detector.detect_transaction_anomaly(tx)
            detection_time = time.time() - start
            
            detection_times.append(detection_time * 1000)  # Convert to ms
        
        total_time = time.time() - start_total
        
        avg_latency = np.mean(detection_times)
        p99_latency = np.percentile(detection_times, 99)
        p95_latency = np.percentile(detection_times, 95)
        
        print(f"Average latency: {avg_latency:.2f}ms")
        print(f"P95 latency: {p95_latency:.2f}ms")
        print(f"P99 latency: {p99_latency:.2f}ms")
        print(f"Total time: {total_time:.2f}s")
        
        self.results['threat_detection'] = {
            'average_latency_ms': avg_latency,
            'p95_latency_ms': p95_latency,
            'p99_latency_ms': p99_latency
        }
        
        print()
    
    def benchmark_consensus_latency(self):
        """Benchmark 4: Consensus Decision Latency"""
        print("-" * 70)
        print("BENCHMARK 4: CONSENSUS DECISION LATENCY")
        print("-" * 70 + "\n")
        
        decision_times = []
        test_count = 100
        
        print(f"Testing consensus decisions {test_count} times...\n")
        
        for i in range(test_count):
            metrics = NetworkMetrics(
                online_nodes=np.random.randint(50, 100),
                total_nodes=100,
                avg_latency_ms=np.random.randint(10, 100),
                transaction_backlog=np.random.randint(100, 5000),
                threat_level=np.random.randint(10, 50),
                recent_attacks=np.random.randint(0, 3)
            )
            
            start = time.time()
            self.consensus.update_metrics(metrics)
            decision_time = time.time() - start
            
            decision_times.append(decision_time * 1000)
        
        avg_decision_time = np.mean(decision_times)
        max_decision_time = np.max(decision_times)
        
        print(f"Average decision time: {avg_decision_time:.2f}ms")
        print(f"Max decision time: {max_decision_time:.2f}ms")
        
        self.results['consensus_latency'] = {
            'average_time_ms': avg_decision_time,
            'max_time_ms': max_decision_time
        }
        
        print()
    
    def benchmark_memory_usage(self):
        """Benchmark 5: Memory Usage"""
        print("-" * 70)
        print("BENCHMARK 5: MEMORY USAGE")
        print("-" * 70 + "\n")
        
        process = psutil.Process()
        
        # Initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"Initial memory: {initial_memory:.2f} MB\n")
        
        # Collect training data
        print("Collecting 10,000 training samples...")
        for i in range(10000):
            features = np.random.randn(90)
            self.learning_engine.collect_training_data(features, 0, 0.8)
        
        after_training = process.memory_info().rss / 1024 / 1024
        print(f"After training data: {after_training:.2f} MB")
        
        # Create many transactions
        print("\nProcessing 1,000 transactions...")
        for i in range(1000):
            tx = {
                'from': f'0x{i:04x}',
                'to': f'0x{i+1:04x}',
                'amount': i,
                'gas_limit': 21000
            }
            _ = self.threat_detector.detect_transaction_anomaly(tx)
        
        after_transactions = process.memory_info().rss / 1024 / 1024
        print(f"After transactions: {after_transactions:.2f} MB")
        
        total_increase = after_transactions - initial_memory
        print(f"\nTotal memory increase: {total_increase:.2f} MB")
        print(f"Memory efficiency: {(total_increase / 10000):.4f} MB per 10k samples")
        
        self.results['memory_usage'] = {
            'initial_mb': initial_memory,
            'after_training_mb': after_training,
            'after_transactions_mb': after_transactions,
            'total_increase_mb': total_increase
        }
        
        print()
    
    def benchmark_learning_performance(self):
        """Benchmark 6: Learning Engine Performance"""
        print("-" * 70)
        print("BENCHMARK 6: LEARNING ENGINE PERFORMANCE")
        print("-" * 70 + "\n")
        
        print("Testing learning engine startup...")
        start = time.time()
        self.learning_engine.start_learning_loop()
        startup_time = time.time() - start
        print(f"Startup time: {startup_time:.3f}s")
        
        print("\nCollecting training data...")
        start = time.time()
        for i in range(5000):
            features = np.random.randn(90)
            self.learning_engine.collect_training_data(features, np.random.randint(0, 4), 0.8)
        collection_time = time.time() - start
        print(f"Collection time for 5000 samples: {collection_time:.3f}s")
        
        print("\nTesting shutdown...")
        start = time.time()
        self.learning_engine.stop_learning_loop()
        shutdown_time = time.time() - start
        print(f"Shutdown time: {shutdown_time:.3f}s")
        
        self.results['learning_performance'] = {
            'startup_time_seconds': startup_time,
            'collection_time_seconds': collection_time,
            'shutdown_time_seconds': shutdown_time,
            'samples_per_second': 5000 / collection_time
        }
        
        print()
    
    def print_benchmark_summary(self):
        """Print benchmark summary"""
        print("\n" + "="*70)
        print("📊 PERFORMANCE BENCHMARK SUMMARY")
        print("="*70 + "\n")
        
        print("Results:")
        print("-" * 70)
        
        for benchmark_name, metrics in self.results.items():
            print(f"\n{benchmark_name.upper().replace('_', ' ')}:")
            for metric_name, value in metrics.items():
                if isinstance(value, float):
                    print(f"  {metric_name}: {value:.2f}")
                elif isinstance(value, dict):
                    print(f"  {metric_name}:")
                    for k, v in value.items():
                        print(f"    {k}: {v:.2f}")
                else:
                    print(f"  {metric_name}: {value}")
        
        print("\n" + "="*70)
        print("🎯 BENCHMARK COMPLETE!")
        print("="*70 + "\n")


if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_all_benchmarks()
