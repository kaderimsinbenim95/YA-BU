#!/usr/bin/env python3
"""
Self-Learning Engine

Continuously learns from network events and improves threat detection models
auomatically without manual intervention.
"""

import numpy as np
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import threading
import time


class LearningPhase(Enum):
    """Learning cycle phases"""
    DATA_COLLECTION = "collecting"      # Collecting training data
    PREPROCESSING = "preprocessing"      # Cleaning and preparing data
    TRAINING = "training"                # Training model
    EVALUATION = "evaluation"            # Evaluating performance
    DEPLOYMENT = "deployment"            # Deploying new model
    MONITORING = "monitoring"            # Monitoring performance


@dataclass
class TrainingData:
    """Represents training example"""
    timestamp: float
    features: np.ndarray
    label: int  # 0=normal, 1=suspicious, 2=threat, 3=critical
    confidence: float
    actual_label: Optional[int] = None  # Ground truth after verification
    feedback_timestamp: Optional[float] = None


@dataclass
class ModelVersion:
    """Represents a model version"""
    version_id: int
    created_at: float
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    training_samples: int
    parameters: Dict
    status: str  # active, archived, testing


class SelfLearningEngine:
    """Continuously self-learning threat detection system"""
    
    def __init__(self, initial_model_params: Dict = None):
        self.current_phase = LearningPhase.MONITORING
        
        # Training data
        self.training_data: List[TrainingData] = []
        self.max_training_samples = 100000
        
        # Model versions
        self.model_versions: List[ModelVersion] = []
        self.current_model_version = 0
        
        # Learning configuration
        self.learning_config = {
            "training_interval_hours": 24,      # Retrain every 24 hours
            "min_samples_for_training": 100,     # Minimum samples to trigger training
            "accuracy_improvement_threshold": 0.02,  # 2% improvement required
            "retraining_patience": 3,            # Patience before forced retraining
            "learning_rate": 0.01,
            "batch_size": 32,
            "epochs": 10
        }
        
        # Performance tracking
        self.performance_history: Dict[str, List[float]] = {
            "accuracy": [],
            "precision": [],
            "recall": [],
            "f1_score": []
        }
        
        # Feedback mechanism
        self.pending_feedback: List[Dict] = []
        self.feedback_processed = 0
        
        # Model parameters
        self.model_params = initial_model_params or self._initialize_model_params()
        
        # Threading for background learning
        self.learning_thread = None
        self.is_learning = False
        self.learning_active = False
        
        # Metrics
        self.metrics = {
            "data_collected": 0,
            "models_trained": 0,
            "improvements_made": 0,
            "last_training_time": None,
            "next_training_time": time.time() + 3600  # 1 hour from now
        }
        
        # Initialize first model version
        self._create_model_version(status="active")
    
    def _initialize_model_params(self) -> Dict:
        """Initialize neural network parameters"""
        return {
            "input_neurons": 90,
            "hidden_layer_1": 64,
            "hidden_layer_2": 32,
            "output_neurons": 4,  # 4 threat classes
            "weights_l1": np.random.randn(90, 64) * 0.01,
            "weights_l2": np.random.randn(64, 32) * 0.01,
            "weights_out": np.random.randn(32, 4) * 0.01,
            "bias_l1": np.zeros((1, 64)),
            "bias_l2": np.zeros((1, 32)),
            "bias_out": np.zeros((1, 4))
        }
    
    def start_learning_loop(self):
        """Start background learning thread"""
        if not self.learning_active:
            self.learning_active = True
            self.learning_thread = threading.Thread(target=self._learning_loop, daemon=True)
            self.learning_thread.start()
            print("[Learning] Self-learning engine started")
    
    def stop_learning_loop(self):
        """Stop background learning thread"""
        self.learning_active = False
        if self.learning_thread:
            self.learning_thread.join(timeout=5)
        print("[Learning] Self-learning engine stopped")
    
    def _learning_loop(self):
        """Main learning loop running in background"""
        patience_counter = 0
        
        while self.learning_active:
            try:
                current_time = time.time()
                
                # Check if it's time to train
                if current_time >= self.metrics["next_training_time"]:
                    # Check if we have enough data
                    if len(self.training_data) >= self.learning_config["min_samples_for_training"]:
                        self._execute_learning_cycle()
                        patience_counter = 0
                    else:
                        patience_counter += 1
                        print(f"[Learning] Not enough data. Samples: {len(self.training_data)}/{self.learning_config['min_samples_for_training']}")
                        
                        # Force training if patience exceeded
                        if patience_counter >= self.learning_config["retraining_patience"]:
                            print("[Learning] Patience exceeded, forcing training with available data")
                            self._execute_learning_cycle()
                            patience_counter = 0
                
                # Process feedback
                self._process_pending_feedback()
                
                # Sleep for 30 seconds before checking again
                time.sleep(30)
                
            except Exception as e:
                print(f"[Learning ERROR] {e}")
                time.sleep(60)
    
    def _execute_learning_cycle(self):
        """Execute complete learning cycle"""
        print("\n" + "="*60)
        print(f"[Learning] Starting Learning Cycle at {datetime.now()}")
        print("="*60)
        
        try:
            # Phase 1: Data Collection
            self._transition_phase(LearningPhase.DATA_COLLECTION)
            print(f"[Learning] Data collected: {len(self.training_data)} samples")
            
            # Phase 2: Preprocessing
            self._transition_phase(LearningPhase.PREPROCESSING)
            processed_data = self._preprocess_data()
            print(f"[Learning] Data preprocessed: {len(processed_data)} valid samples")
            
            if len(processed_data) < self.learning_config["min_samples_for_training"]:
                print("[Learning] Not enough processed data")
                return
            
            # Phase 3: Training
            self._transition_phase(LearningPhase.TRAINING)
            old_version_id = self.current_model_version
            self._train_model(processed_data)
            print(f"[Learning] Model trained successfully")
            
            # Phase 4: Evaluation
            self._transition_phase(LearningPhase.EVALUATION)
            metrics = self._evaluate_model(processed_data)
            print(f"[Learning] Model evaluated - Accuracy: {metrics['accuracy']:.3f}")
            
            # Phase 5: Deployment Decision
            if self._should_deploy_model(metrics):
                self._transition_phase(LearningPhase.DEPLOYMENT)
                self._deploy_model(metrics)
                print(f"[Learning] ✅ New model deployed! Version {self.current_model_version}")
                self.metrics["improvements_made"] += 1
            else:
                print(f"[Learning] Model not better than current version, keeping version {old_version_id}")
            
            # Phase 6: Monitoring
            self._transition_phase(LearningPhase.MONITORING)
            
            # Schedule next training
            next_training = time.time() + self.learning_config["training_interval_hours"] * 3600
            self.metrics["next_training_time"] = next_training
            self.metrics["last_training_time"] = time.time()
            self.metrics["models_trained"] += 1
            
            # Clear old data after training
            self._cleanup_old_data()
            
            print("[Learning] Learning cycle completed successfully")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"[Learning ERROR] Learning cycle failed: {e}")
            self._transition_phase(LearningPhase.MONITORING)
    
    def collect_training_data(self, features: np.ndarray, predicted_label: int, confidence: float):
        """Collect data point for training"""
        training_point = TrainingData(
            timestamp=time.time(),
            features=features,
            label=predicted_label,
            confidence=confidence
        )
        
        self.training_data.append(training_point)
        self.metrics["data_collected"] += 1
        
        # Limit memory usage
        if len(self.training_data) > self.max_training_samples:
            # Keep most recent samples
            self.training_data = self.training_data[-self.max_training_samples:]
    
    def add_feedback(self, predicted_label: int, actual_label: int, features: np.ndarray):
        """Add human/system feedback about prediction"""
        feedback = {
            "timestamp": time.time(),
            "predicted": predicted_label,
            "actual": actual_label,
            "features": features,
            "processed": False
        }
        
        self.pending_feedback.append(feedback)
    
    def _process_pending_feedback(self):
        """Process pending feedback and update training data"""
        for feedback in self.pending_feedback:
            if not feedback["processed"]:
                # Find corresponding training data
                for data in self.training_data:
                    if abs(data.timestamp - feedback["timestamp"]) < 1.0:
                        data.actual_label = feedback["actual"]
                        data.feedback_timestamp = time.time()
                        break
                
                feedback["processed"] = True
                self.feedback_processed += 1
    
    def _preprocess_data(self) -> List[Tuple[np.ndarray, int]]:
        """Preprocess and clean training data"""
        processed = []
        
        for data in self.training_data:
            # Skip incomplete data
            if data.features is None or len(data.features) == 0:
                continue
            
            # Use actual label if available, otherwise use predicted
            label = data.actual_label if data.actual_label is not None else data.label
            
            # Normalize features
            normalized_features = self._normalize_features(data.features)
            
            processed.append((normalized_features, label))
        
        return processed
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """Normalize features to 0-1 range"""
        if len(features) == 0:
            return features
        
        min_val = np.min(features)
        max_val = np.max(features)
        
        if max_val - min_val == 0:
            return np.zeros_like(features)
        
        return (features - min_val) / (max_val - min_val)
    
    def _train_model(self, training_data: List[Tuple[np.ndarray, int]]):
        """Train the neural network model"""
        print(f"[Training] Training with {len(training_data)} samples...")
        
        # Batch training
        batch_size = self.learning_config["batch_size"]
        learning_rate = self.learning_config["learning_rate"]
        epochs = self.learning_config["epochs"]
        
        for epoch in range(epochs):
            # Shuffle data
            indices = np.random.permutation(len(training_data))
            
            for i in range(0, len(training_data), batch_size):
                batch_indices = indices[i:i+batch_size]
                
                # Get batch
                batch_X = np.array([training_data[j][0] for j in batch_indices])
                batch_y = np.array([training_data[j][1] for j in batch_indices])
                
                # Forward pass (simplified)
                self._forward_pass(batch_X)
                
                # Backward pass (simplified) - update weights
                self._backward_pass(batch_X, batch_y, learning_rate)
            
            print(f"[Training] Epoch {epoch+1}/{epochs} completed")
    
    def _forward_pass(self, X: np.ndarray) -> np.ndarray:
        """Forward pass through network"""
        # Layer 1
        z1 = np.dot(X, self.model_params["weights_l1"]) + self.model_params["bias_l1"]
        a1 = self._relu(z1)
        
        # Layer 2
        z2 = np.dot(a1, self.model_params["weights_l2"]) + self.model_params["bias_l2"]
        a2 = self._relu(z2)
        
        # Output layer
        z3 = np.dot(a2, self.model_params["weights_out"]) + self.model_params["bias_out"]
        a3 = self._softmax(z3)
        
        return a3
    
    def _backward_pass(self, X: np.ndarray, y: np.ndarray, learning_rate: float):
        """Backward pass and weight updates (simplified)"""
        # Simplified gradient descent
        self.model_params["weights_out"] -= learning_rate * 0.01
        self.model_params["weights_l2"] -= learning_rate * 0.01
        self.model_params["weights_l1"] -= learning_rate * 0.01
    
    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation function"""
        return np.maximum(0, x)
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax activation function"""
        exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=1, keepdims=True)
    
    def _evaluate_model(self, test_data: List[Tuple[np.ndarray, int]]) -> Dict:
        """Evaluate model performance"""
        predictions = []
        actuals = []
        
        for features, label in test_data:
            output = self._forward_pass(np.array([features]))
            pred = np.argmax(output)
            predictions.append(pred)
            actuals.append(label)
        
        # Calculate metrics
        accuracy = np.mean(np.array(predictions) == np.array(actuals))
        
        # Simple precision and recall
        tp = np.sum((np.array(predictions) == 1) & (np.array(actuals) == 1))
        fp = np.sum((np.array(predictions) == 1) & (np.array(actuals) != 1))
        fn = np.sum((np.array(predictions) != 1) & (np.array(actuals) == 1))
        
        precision = tp / (tp + fp + 1e-10)
        recall = tp / (tp + fn + 1e-10)
        f1 = 2 * (precision * recall) / (precision + recall + 1e-10)
        
        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }
        
        # Store in history
        for key, value in metrics.items():
            self.performance_history[key].append(value)
        
        return metrics
    
    def _should_deploy_model(self, new_metrics: Dict) -> bool:
        """Determine if new model should be deployed"""
        if not self.model_versions:
            return True
        
        current_model = self.model_versions[self.current_model_version]
        improvement = new_metrics["accuracy"] - current_model.accuracy
        
        return improvement >= self.learning_config["accuracy_improvement_threshold"]
    
    def _deploy_model(self, metrics: Dict):
        """Deploy new model version"""
        self._create_model_version(
            status="active",
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1_score=metrics["f1_score"]
        )
    
    def _create_model_version(self, status: str = "active", accuracy: float = 0.0,
                             precision: float = 0.0, recall: float = 0.0, f1_score: float = 0.0):
        """Create new model version"""
        version = ModelVersion(
            version_id=len(self.model_versions),
            created_at=time.time(),
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            training_samples=len(self.training_data),
            parameters=dict(self.model_params),
            status=status
        )
        
        # Archive old versions if new is active
        if status == "active":
            for v in self.model_versions:
                if v.status == "active":
                    v.status = "archived"
            self.current_model_version = version.version_id
        
        self.model_versions.append(version)
        print(f"[Model] Version {version.version_id} created - Accuracy: {accuracy:.3f}")
    
    def _cleanup_old_data(self):
        """Clean up old training data to save memory"""
        # Keep only recent data
        cutoff_time = time.time() - (7 * 24 * 3600)  # 7 days
        
        self.training_data = [
            data for data in self.training_data
            if data.timestamp > cutoff_time
        ]
        
        print(f"[Learning] Cleaned up old data. Remaining samples: {len(self.training_data)}")
    
    def _transition_phase(self, phase: LearningPhase):
        """Transition to new learning phase"""
        self.current_phase = phase
        print(f"[Phase] Transitioning to: {phase.value}")
    
    def get_learning_status(self) -> Dict:
        """Get current learning status"""
        return {
            "current_phase": self.current_phase.value,
            "training_samples": len(self.training_data),
            "models_trained": self.metrics["models_trained"],
            "improvements_made": self.metrics["improvements_made"],
            "current_model_version": self.current_model_version,
            "last_training_time": self.metrics["last_training_time"],
            "next_training_time": self.metrics["next_training_time"],
            "feedback_processed": self.feedback_processed,
            "performance_history": self.performance_history,
            "is_active": self.learning_active
        }
    
    def get_model_versions(self) -> List[Dict]:
        """Get all model versions"""
        return [asdict(v) for v in self.model_versions]


if __name__ == "__main__":
    # Example usage
    engine = SelfLearningEngine()
    
    # Start learning loop
    engine.start_learning_loop()
    
    # Simulate data collection
    print("\n[Demo] Simulating threat detection and learning...\n")
    
    for i in range(200):
        # Generate random features
        features = np.random.randn(90)
        predicted_label = np.random.randint(0, 4)
        confidence = np.random.uniform(0.5, 1.0)
        
        # Collect training data
        engine.collect_training_data(features, predicted_label, confidence)
        
        # Occasionally add feedback
        if i % 10 == 0:
            actual_label = predicted_label  # Assume mostly correct
            engine.add_feedback(predicted_label, actual_label, features)
        
        time.sleep(0.1)
    
    # Wait for learning to complete
    print("\n[Demo] Waiting for learning cycle...\n")
    time.sleep(10)
    
    # Check status
    status = engine.get_learning_status()
    print("\n[Demo] Learning Status:")
    print(json.dumps(status, indent=2, default=str))
    
    # Stop learning
    engine.stop_learning_loop()
