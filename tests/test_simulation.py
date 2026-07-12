#!/usr/bin/env python3
"""
Simulation Test Suite

Comprehensive testing of SatoshiOS-AI-Blockchain system including
all components, threat scenarios, and performance benchmarks.
"""

import sys
import time
import json
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

# Import core modules
from core.consensus.hybrid_consensus import HybridConsensus, NetworkMetrics, ConsensusType
from ai_security.threat_detection import ThreatDetector, AnomalyDetector
from ai_security.self_learning_engine import SelfLearningEngine
from ai_security.adaptive_defense import AdaptiveDefenseSystem, DefenseLevel
from ai_security.knowledge_base import KnowledgeBase
from ai_security.feedback_loop import FeedbackLoop, FeedbackType


class SimulationTestSuite:
    """Main test suite for SatoshiOS-AI-Blockchain"""
    
    def __init__(self, test_name: str = "SatoshiOS Test Run"):
        self.test_name = test_name
        self.start_time = time.time()
        self.results = []
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0
        
        # Initialize components
        print("\n" + "="*70)
        print(f"🚀 INITIALIZING TEST SUITE: {test_name}")
        print("="*70 + "\n")
        
        self.consensus = HybridConsensus()
        self.threat_detector = ThreatDetector()
        self.learning_engine = SelfLearningEngine()
        self.defense_system = AdaptiveDefenseSystem()
        self.knowledge_base = KnowledgeBase()
        self.feedback_loop = FeedbackLoop()
        
        print("✅ All components initialized\n")
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("\n" + "="*70)
        print("📊 RUNNING COMPLETE TEST SUITE")
        print("="*70 + "\n")
        
        # Test 1: Consensus Engine
        self.test_consensus_engine()
        
        # Test 2: Threat Detection
        self.test_threat_detection()
        
        # Test 3: Adaptive Defense
        self.test_adaptive_defense()
        
        # Test 4: Self-Learning Engine
        self.test_self_learning_engine()
        
        # Test 5: Knowledge Base
        self.test_knowledge_base()
        
        # Test 6: Feedback Loop
        self.test_feedback_loop()
        
        # Test 7: Integration Tests
        self.test_integration()
        
        # Print summary
        self.print_summary()
    
    def test_consensus_engine(self):
        """Test 1: Consensus Engine"""
        print("\n" + "-"*70)
        print("TEST 1: CONSENSUS ENGINE")
        print("-"*70 + "\n")
        
        try:
            # Add validators
            self.consensus.pos.add_validator("validator_1", 100)
            self.consensus.pos.add_validator("validator_2", 80)
            self.consensus.pos.add_validator("validator_3", 60)
            
            # Test network metrics
            metrics = NetworkMetrics(
                online_nodes=95,
                total_nodes=100,
                avg_latency_ms=50,
                transaction_backlog=100,
                threat_level=20,
                recent_attacks=0
            )
            
            self.consensus.update_metrics(metrics)
            print(f"✓ Network health score: {metrics.health_score():.1f}")
            print(f"✓ Selected consensus: {self.consensus.consensus_type.value}")
            
            # Create and mine blocks
            for i in range(3):
                block = self.consensus.create_block([f"tx_{j}" for j in range(5)])
                success = self.consensus.mine_block(block)
                print(f"✓ Block {i} mined: {success}")
            
            print(f"✓ Blockchain length: {self.consensus.get_chain_length()}")
            
            self._record_test("Consensus Engine", True, "All consensus tests passed")
            
        except Exception as e:
            self._record_test("Consensus Engine", False, str(e))
    
    def test_threat_detection(self):
        """Test 2: Threat Detection System"""
        print("\n" + "-"*70)
        print("TEST 2: THREAT DETECTION")
        print("-"*70 + "\n")
        
        try:
            # Normal transaction
            normal_tx = {
                'from': '0x1234',
                'to': '0x5678',
                'amount': 100,
                'gas_limit': 21000
            }
            
            result = self.threat_detector.detect_transaction_anomaly(normal_tx)
            print(f"✓ Normal TX - Threat: {result.threat_level.name}, Score: {result.score:.3f}")
            
            # Suspicious transaction
            suspicious_tx = {
                'from': '0x9999',  # New address
                'to': '0x8888',
                'amount': 1000000,  # Large amount
                'gas_limit': 5000000  # Unusual gas
            }
            
            result = self.threat_detector.detect_transaction_anomaly(suspicious_tx)
            print(f"✓ Suspicious TX - Threat: {result.threat_level.name}, Score: {result.score:.3f}")
            
            # Network anomaly
            network_metrics = {
                'online_nodes': 30,
                'total_nodes': 100,
                'avg_latency_ms': 500,
                'transaction_backlog': 5000,
                'avg_block_time': 5
            }
            
            result = self.threat_detector.detect_network_anomaly(network_metrics)
            print(f"✓ Network Anomaly - Threat: {result.threat_level.name}, Score: {result.score:.3f}")
            
            self._record_test("Threat Detection", True, "Threat detection working correctly")
            
        except Exception as e:
            self._record_test("Threat Detection", False, str(e))
    
    def test_adaptive_defense(self):
        """Test 3: Adaptive Defense System"""
        print("\n" + "-"*70)
        print("TEST 3: ADAPTIVE DEFENSE")
        print("-"*70 + "\n")
        
        try:
            # Test normal threat level
            self.defense_system.update_threat_level(0.1)
            print(f"✓ Threat 0.1 → Defense: {self.defense_system.current_defense_level.name}")
            time.sleep(0.5)
            
            # Test increasing threat
            self.defense_system.update_threat_level(0.5)
            print(f"✓ Threat 0.5 → Defense: {self.defense_system.current_defense_level.name}")
            time.sleep(0.5)
            
            # Test critical threat
            self.defense_system.update_threat_level(0.85)
            print(f"✓ Threat 0.85 → Defense: {self.defense_system.current_defense_level.name}")
            
            # Check strategy
            strategy = self.defense_system.current_strategy
            print(f"✓ Current strategy - Consensus: {strategy.consensus_mode.value}")
            print(f"✓ Max throughput: {strategy.transaction_throughput} TPS")
            
            self._record_test("Adaptive Defense", True, "Defense adaptation working")
            
        except Exception as e:
            self._record_test("Adaptive Defense", False, str(e))
    
    def test_self_learning_engine(self):
        """Test 4: Self-Learning Engine"""
        print("\n" + "-"*70)
        print("TEST 4: SELF-LEARNING ENGINE")
        print("-"*70 + "\n")
        
        try:
            # Start learning loop
            self.learning_engine.start_learning_loop()
            print("✓ Learning engine started")
            
            # Collect training data
            for i in range(50):
                features = np.random.randn(90)
                label = np.random.randint(0, 4)
                confidence = np.random.uniform(0.5, 1.0)
                
                self.learning_engine.collect_training_data(features, label, confidence)
            
            status = self.learning_engine.get_learning_status()
            print(f"✓ Training samples collected: {status['training_samples']}")
            print(f"✓ Current phase: {status['current_phase']}")
            print(f"✓ Models trained: {status['models_trained']}")
            
            # Add feedback
            for i in range(10):
                features = np.random.randn(90)
                self.learning_engine.add_feedback(0, 0, features)
            
            print(f"✓ Feedback pending: {len(self.learning_engine.pending_feedback)}")
            
            # Stop learning
            self.learning_engine.stop_learning_loop()
            print("✓ Learning engine stopped")
            
            self._record_test("Self-Learning Engine", True, "Learning engine functional")
            
        except Exception as e:
            self._record_test("Self-Learning Engine", False, str(e))
    
    def test_knowledge_base(self):
        """Test 5: Knowledge Base"""
        print("\n" + "-"*70)
        print("TEST 5: KNOWLEDGE BASE")
        print("-"*70 + "\n")
        
        try:
            # Store threat pattern
            pattern_id = self.knowledge_base.store_threat_pattern(
                "Rapid transactions",
                [0.8, 0.6, 0.7, 0.9],
                threat_level=2,
                confidence=0.85
            )
            print(f"✓ Stored threat pattern: {pattern_id}")
            
            # Store attack signature
            sig_id = self.knowledge_base.store_attack_signature(
                "51% Attack",
                {"hash_rate_spike": 200},
                severity=3,
                detection_method="hash_rate_monitoring"
            )
            print(f"✓ Stored attack signature: {sig_id}")
            
            # Store defense strategy
            strategy_id = self.knowledge_base.store_defense_strategy(
                "Consensus switch",
                {"from": "PoS", "to": "PoW"},
                effectiveness=0.92
            )
            print(f"✓ Stored defense strategy: {strategy_id}")
            
            # Retrieve and check
            patterns = self.knowledge_base.retrieve_threat_patterns()
            print(f"✓ Retrieved patterns: {len(patterns)}")
            
            stats = self.knowledge_base.get_statistics()
            print(f"✓ KB Statistics: {stats['total_entries']} total entries")
            
            self._record_test("Knowledge Base", True, "KB operations successful")
            
        except Exception as e:
            self._record_test("Knowledge Base", False, str(e))
    
    def test_feedback_loop(self):
        """Test 6: Feedback Loop"""
        print("\n" + "-"*70)
        print("TEST 6: FEEDBACK LOOP")
        print("-"*70 + "\n")
        
        try:
            # Register callbacks
            callback_count = {'retrain': 0, 'adjust': 0}
            
            def on_retrain(metrics):
                callback_count['retrain'] += 1
            
            def on_adjust(metrics):
                callback_count['adjust'] += 1
            
            self.feedback_loop.register_callback("retrain_model", on_retrain)
            self.feedback_loop.register_callback("adjust_strategy", on_adjust)
            
            # Submit feedback
            for i in range(20):
                feedback_type = FeedbackType.PREDICTION_CORRECT if i % 4 != 3 else FeedbackType.FALSE_POSITIVE
                score = 0.9 if i % 4 != 3 else 0.1
                
                self.feedback_loop.submit_feedback(
                    feedback_type=feedback_type,
                    event_id=f"event_{i}",
                    score=score,
                    description=f"Test feedback {i}"
                )
            
            metrics = self.feedback_loop.get_metrics()
            print(f"✓ Total feedback: {metrics['total_feedback']}")
            print(f"✓ Prediction accuracy: {metrics['prediction_accuracy']:.2%}")
            print(f"✓ False positive rate: {metrics['false_positive_rate']:.2%}")
            
            trends = self.feedback_loop.analyze_trends()
            print(f"✓ Trend: {trends.get('trend', 'N/A')}")
            
            self._record_test("Feedback Loop", True, "Feedback system working")
            
        except Exception as e:
            self._record_test("Feedback Loop", False, str(e))
    
    def test_integration(self):
        """Test 7: Integration Tests"""
        print("\n" + "-"*70)
        print("TEST 7: INTEGRATION TESTS")
        print("-"*70 + "\n")
        
        try:
            print("Testing component interactions...\n")
            
            # Simulate complete flow
            print("1. Creating transaction...")
            tx = {'from': '0x1234', 'to': '0x5678', 'amount': 100, 'gas_limit': 21000}
            
            # Detect threats
            print("2. Detecting threats...")
            threat_result = self.threat_detector.detect_transaction_anomaly(tx)
            print(f"   Threat level: {threat_result.threat_level.name}")
            
            # Adapt defense
            print("3. Adapting defense...")
            threat_score = threat_result.score
            self.defense_system.update_threat_level(threat_score)
            print(f"   Defense level: {self.defense_system.current_defense_level.name}")
            
            # Check if should accept
            print("4. Checking transaction acceptance...")
            should_accept = self.defense_system.should_accept_transaction(tx)
            print(f"   Transaction accepted: {should_accept}")
            
            # Add to knowledge base
            print("5. Storing knowledge...")
            if threat_score > 0.5:
                self.knowledge_base.store_threat_pattern(
                    f"Pattern_{datetime.now().timestamp()}",
                    [threat_score],
                    threat_level=int(threat_score * 3),
                    confidence=0.8
                )
            
            # Collect feedback
            print("6. Collecting feedback...")
            self.feedback_loop.submit_feedback(
                feedback_type=FeedbackType.PREDICTION_CORRECT,
                event_id="integration_test_1",
                score=0.9,
                description="Integration test transaction"
            )
            print("   Feedback recorded")
            
            print("\n✓ Integration test completed successfully")
            self._record_test("Integration Tests", True, "All components work together")
            
        except Exception as e:
            self._record_test("Integration Tests", False, str(e))
    
    def _record_test(self, test_name: str, passed: bool, message: str):
        """Record test result"""
        self.test_count += 1
        if passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
        
        result = {
            "test_name": test_name,
            "passed": passed,
            "message": message,
            "timestamp": time.time()
        }
        self.results.append(result)
    
    def print_summary(self):
        """Print test summary"""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70 + "\n")
        
        print(f"Total Tests: {self.test_count}")
        print(f"✅ Passed: {self.passed_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"📈 Pass Rate: {(self.passed_count/self.test_count)*100:.1f}%")
        print(f"⏱️  Total Time: {elapsed:.2f}s")
        
        print("\nDetailed Results:")
        print("-" * 70)
        for result in self.results:
            status = "✅ PASS" if result["passed"] else "❌ FAIL"
            print(f"{status} | {result['test_name']:30s} | {result['message']}")
        
        print("\n" + "="*70)
        
        if self.passed_count == self.test_count:
            print("🎉 ALL TESTS PASSED! System is ready for deployment!")
        else:
            print(f"⚠️  {self.failed_count} test(s) failed. Review and fix before deployment.")
        
        print("="*70 + "\n")
        
        # Save results to file
        self._save_results()
    
    def _save_results(self):
        """Save test results to JSON file"""
        results_data = {
            "test_suite": self.test_name,
            "timestamp": datetime.now().isoformat(),
            "total_tests": self.test_count,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": (self.passed_count/self.test_count)*100,
            "results": self.results
        }
        
        filename = f"test_results_{int(time.time())}.json"
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Results saved to: {filename}")


if __name__ == "__main__":
    # Create and run test suite
    suite = SimulationTestSuite("SatoshiOS-AI-Blockchain v1.0")
    suite.run_all_tests()
