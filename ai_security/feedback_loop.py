#!/usr/bin/env python3
"""
Feedback Loop System

Collects feedback on predictions and defense actions, measures effectiveness,
and triggers improvements.
"""

import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class FeedbackType(Enum):
    """Types of feedback"""
    PREDICTION_CORRECT = "prediction_correct"
    PREDICTION_WRONG = "prediction_wrong"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    DEFENSE_EFFECTIVE = "defense_effective"
    DEFENSE_INEFFECTIVE = "defense_ineffective"
    SYSTEM_PERFORMANCE = "system_performance"


@dataclass
class Feedback:
    """Feedback entry"""
    feedback_type: FeedbackType
    timestamp: float
    related_event_id: str
    score: float  # 0.0-1.0
    description: str
    metadata: Dict


class FeedbackLoop:
    """Manages feedback collection and processing"""
    
    def __init__(self):
        self.feedback_queue: List[Feedback] = []
        self.feedback_history: List[Feedback] = []
        self.max_history = 100000
        
        # Metrics
        self.metrics = {
            "total_feedback": 0,
            "correct_predictions": 0,
            "wrong_predictions": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "effective_defenses": 0,
            "ineffective_defenses": 0
        }
        
        # Thresholds for triggering actions
        self.action_triggers = {
            "false_positive_rate": 0.1,  # If FP rate > 10%
            "prediction_accuracy": 0.85,  # Target accuracy
            "defense_effectiveness": 0.8  # Target effectiveness
        }
        
        # Callbacks for actions
        self.callbacks: Dict[str, List[Callable]] = {
            "retrain_model": [],
            "adjust_strategy": [],
            "alert_administrator": [],
            "update_parameters": []
        }
    
    def submit_feedback(self, feedback_type: FeedbackType, event_id: str,
                       score: float, description: str, metadata: Dict = None) -> str:
        """Submit feedback about a system event"""
        feedback = Feedback(
            feedback_type=feedback_type,
            timestamp=time.time(),
            related_event_id=event_id,
            score=score,
            description=description,
            metadata=metadata or {}
        )
        
        self.feedback_queue.append(feedback)
        self.feedback_history.append(feedback)
        
        # Maintain history size
        if len(self.feedback_history) > self.max_history:
            self.feedback_history = self.feedback_history[-self.max_history:]
        
        # Update metrics
        self._update_metrics(feedback)
        
        # Check if action should be triggered
        self._check_action_triggers()
        
        print(f"[Feedback] Recorded: {feedback_type.value} (Score: {score:.2f})")
        return event_id
    
    def _update_metrics(self, feedback: Feedback):
        """Update metrics based on feedback"""
        self.metrics["total_feedback"] += 1
        
        if feedback.feedback_type == FeedbackType.PREDICTION_CORRECT:
            self.metrics["correct_predictions"] += 1
        elif feedback.feedback_type == FeedbackType.PREDICTION_WRONG:
            self.metrics["wrong_predictions"] += 1
        elif feedback.feedback_type == FeedbackType.FALSE_POSITIVE:
            self.metrics["false_positives"] += 1
        elif feedback.feedback_type == FeedbackType.FALSE_NEGATIVE:
            self.metrics["false_negatives"] += 1
        elif feedback.feedback_type == FeedbackType.DEFENSE_EFFECTIVE:
            self.metrics["effective_defenses"] += 1
        elif feedback.feedback_type == FeedbackType.DEFENSE_INEFFECTIVE:
            self.metrics["ineffective_defenses"] += 1
    
    def _check_action_triggers(self):
        """Check if any actions should be triggered"""
        # Check prediction accuracy
        total_predictions = self.metrics["correct_predictions"] + self.metrics["wrong_predictions"]
        if total_predictions > 0:
            accuracy = self.metrics["correct_predictions"] / total_predictions
            
            if accuracy < self.action_triggers["prediction_accuracy"]:
                self._trigger_action("retrain_model")
        
        # Check false positive rate
        total_negatives = self.metrics["false_positives"] + (self.metrics["correct_predictions"] - self.metrics["false_negatives"])
        if total_negatives > 0:
            fp_rate = self.metrics["false_positives"] / total_negatives
            
            if fp_rate > self.action_triggers["false_positive_rate"]:
                self._trigger_action("adjust_strategy")
        
        # Check defense effectiveness
        total_defenses = self.metrics["effective_defenses"] + self.metrics["ineffective_defenses"]
        if total_defenses > 0:
            effectiveness = self.metrics["effective_defenses"] / total_defenses
            
            if effectiveness < self.action_triggers["defense_effectiveness"]:
                self._trigger_action("update_parameters")
    
    def _trigger_action(self, action_name: str):
        """Trigger action and call registered callbacks"""
        print(f"\n[FeedbackLoop] ⚡ Triggering action: {action_name}")
        
        if action_name in self.callbacks:
            for callback in self.callbacks[action_name]:
                try:
                    callback(self.get_metrics())
                except Exception as e:
                    print(f"[FeedbackLoop ERROR] Callback failed: {e}")
    
    def register_callback(self, action_name: str, callback: Callable):
        """Register callback for action"""
        if action_name not in self.callbacks:
            self.callbacks[action_name] = []
        
        self.callbacks[action_name].append(callback)
        print(f"[FeedbackLoop] Registered callback for {action_name}")
    
    def get_metrics(self) -> Dict:
        """Get current feedback metrics"""
        total_predictions = self.metrics["correct_predictions"] + self.metrics["wrong_predictions"]
        total_defenses = self.metrics["effective_defenses"] + self.metrics["ineffective_defenses"]
        
        accuracy = (self.metrics["correct_predictions"] / total_predictions) if total_predictions > 0 else 0
        false_positive_rate = (self.metrics["false_positives"] / (self.metrics["false_positives"] + self.metrics["correct_predictions"] - self.metrics["false_negatives"])) if total_predictions > 0 else 0
        defense_effectiveness = (self.metrics["effective_defenses"] / total_defenses) if total_defenses > 0 else 0
        
        return {
            "total_feedback": self.metrics["total_feedback"],
            "prediction_accuracy": accuracy,
            "false_positive_rate": false_positive_rate,
            "defense_effectiveness": defense_effectiveness,
            "total_predictions": total_predictions,
            "total_defenses": total_defenses,
            "metrics_detail": self.metrics.copy()
        }
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict]:
        """Get recent feedback entries"""
        recent = self.feedback_history[-limit:]
        return [
            {
                "type": f.feedback_type.value,
                "timestamp": f.timestamp,
                "score": f.score,
                "description": f.description
            }
            for f in reversed(recent)
        ]
    
    def analyze_trends(self, time_window_hours: int = 24) -> Dict:
        """Analyze feedback trends over time"""
        cutoff_time = time.time() - (time_window_hours * 3600)
        
        recent_feedback = [
            f for f in self.feedback_history
            if f.timestamp > cutoff_time
        ]
        
        if not recent_feedback:
            return {"message": "No feedback in time window"}
        
        # Analyze trends
        positive_feedback = sum(1 for f in recent_feedback if f.score > 0.5)
        negative_feedback = sum(1 for f in recent_feedback if f.score <= 0.5)
        
        trend = "improving" if positive_feedback > negative_feedback else "declining"
        
        return {
            "time_window_hours": time_window_hours,
            "feedback_count": len(recent_feedback),
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "trend": trend,
            "positive_ratio": positive_feedback / len(recent_feedback) if recent_feedback else 0
        }


if __name__ == "__main__":
    # Example usage
    feedback_loop = FeedbackLoop()
    
    # Register callbacks
    def on_retrain_model(metrics):
        print("[Callback] Retraining model with current metrics...")
        print(f"  Accuracy: {metrics['prediction_accuracy']:.2%}")
    
    def on_adjust_strategy(metrics):
        print("[Callback] Adjusting defense strategy...")
        print(f"  FP Rate: {metrics['false_positive_rate']:.2%}")
    
    feedback_loop.register_callback("retrain_model", on_retrain_model)
    feedback_loop.register_callback("adjust_strategy", on_adjust_strategy)
    
    print("\n[Demo] Testing Feedback Loop\n")
    
    # Submit feedback
    for i in range(15):
        feedback_type = FeedbackType.PREDICTION_CORRECT if i % 3 != 2 else FeedbackType.FALSE_POSITIVE
        score = 0.9 if i % 3 != 2 else 0.1
        
        feedback_loop.submit_feedback(
            feedback_type=feedback_type,
            event_id=f"event_{i}",
            score=score,
            description=f"Sample feedback {i}"
        )
        time.sleep(0.1)
    
    # Get metrics
    print("\nFeedback Metrics:")
    metrics = feedback_loop.get_metrics()
    import json
    print(json.dumps(metrics, indent=2))
    
    # Analyze trends
    print("\nTrend Analysis:")
    trends = feedback_loop.analyze_trends()
    print(json.dumps(trends, indent=2))
