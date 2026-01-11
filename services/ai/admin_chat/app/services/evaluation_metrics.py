"""
Domain 3.6: Evaluation & KPIs
Objectively measure system quality
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from pathlib import Path


class EvaluationMetrics:
    """
    Core Metrics Tracking and Governance
    """
    
    def __init__(self):
        self._metrics_dir = Path(__file__).parent.parent.parent / "data" / "metrics"
        self._metrics_dir.mkdir(parents=True, exist_ok=True)
        self._metrics_file = self._metrics_dir / "evaluation_metrics.json"
    
    def record_query_metric(self, metric_type: str, value: Any, metadata: Optional[Dict] = None):
        """
        Record a query metric
        
        Args:
            metric_type: Type of metric (sql_validity, answer_correctness, join_accuracy, etc.)
            value: Metric value
            metadata: Additional metadata
        """
        metric_entry = {
            'timestamp': datetime.now().isoformat(),
            'metric_type': metric_type,
            'value': value,
            'metadata': metadata or {}
        }
        
        # Load existing metrics
        metrics_list = []
        if self._metrics_file.exists():
            try:
                with open(self._metrics_file, 'r') as f:
                    metrics_list = json.load(f)
            except:
                metrics_list = []
        
        # Add new metric
        metrics_list.append(metric_entry)
        
        # Keep only last 10000 entries
        if len(metrics_list) > 10000:
            metrics_list = metrics_list[-10000:]
        
        # Save
        try:
            with open(self._metrics_file, 'w') as f:
                json.dump(metrics_list, f, indent=2)
        except Exception as e:
            print(f"Error saving metric: {e}")
    
    def calculate_kpis(self, days: int = 7) -> Dict[str, Any]:
        """
        Calculate KPIs for the last N days
        
        Returns:
            Dictionary with KPI values
        """
        if not self._metrics_file.exists():
            return self._get_empty_kpis()
        
        try:
            with open(self._metrics_file, 'r') as f:
                metrics_list = json.load(f)
        except:
            return self._get_empty_kpis()
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_metrics = [
            m for m in metrics_list
            if datetime.fromisoformat(m['timestamp']) >= cutoff_date
        ]
        
        if not recent_metrics:
            return self._get_empty_kpis()
        
        # Calculate KPIs
        kpis = {
            'sql_validity_rate': self._calculate_sql_validity_rate(recent_metrics),
            'correct_answer_rate': self._calculate_correct_answer_rate(recent_metrics),
            'join_accuracy': self._calculate_join_accuracy(recent_metrics),
            'average_response_time_ms': self._calculate_avg_response_time(recent_metrics),
            'user_satisfaction_score': self._calculate_user_satisfaction(recent_metrics),
            'hallucination_frequency': self._calculate_hallucination_frequency(recent_metrics),
            'total_queries': len(recent_metrics),
            'period_days': days
        }
        
        return kpis
    
    def _calculate_sql_validity_rate(self, metrics: List[Dict]) -> float:
        """Calculate SQL validity rate"""
        sql_metrics = [m for m in metrics if m.get('metric_type') == 'sql_validity']
        if not sql_metrics:
            return 0.0
        
        valid_count = sum(1 for m in sql_metrics if m.get('value') is True)
        return valid_count / len(sql_metrics)
    
    def _calculate_correct_answer_rate(self, metrics: List[Dict]) -> float:
        """Calculate correct answer rate"""
        answer_metrics = [m for m in metrics if m.get('metric_type') == 'answer_correctness']
        if not answer_metrics:
            return 0.0
        
        correct_count = sum(1 for m in answer_metrics if m.get('value') is True)
        return correct_count / len(answer_metrics)
    
    def _calculate_join_accuracy(self, metrics: List[Dict]) -> float:
        """Calculate join accuracy"""
        join_metrics = [m for m in metrics if m.get('metric_type') == 'join_accuracy']
        if not join_metrics:
            return 0.0
        
        accurate_count = sum(1 for m in join_metrics if m.get('value') is True)
        return accurate_count / len(join_metrics)
    
    def _calculate_avg_response_time(self, metrics: List[Dict]) -> float:
        """Calculate average response time"""
        time_metrics = [m for m in metrics if m.get('metric_type') == 'response_time']
        if not time_metrics:
            return 0.0
        
        times = [m.get('value', 0) for m in time_metrics if isinstance(m.get('value'), (int, float))]
        return sum(times) / len(times) if times else 0.0
    
    def _calculate_user_satisfaction(self, metrics: List[Dict]) -> float:
        """Calculate user satisfaction score"""
        satisfaction_metrics = [m for m in metrics if m.get('metric_type') == 'user_satisfaction']
        if not satisfaction_metrics:
            return 0.0
        
        scores = [m.get('value', 0) for m in satisfaction_metrics if isinstance(m.get('value'), (int, float))]
        return sum(scores) / len(scores) if scores else 0.0
    
    def _calculate_hallucination_frequency(self, metrics: List[Dict]) -> float:
        """Calculate hallucination frequency"""
        hallucination_metrics = [m for m in metrics if m.get('metric_type') == 'hallucination']
        if not hallucination_metrics:
            return 0.0
        
        hallucination_count = sum(1 for m in hallucination_metrics if m.get('value') is True)
        return hallucination_count / len(metrics) if metrics else 0.0
    
    def _get_empty_kpis(self) -> Dict[str, Any]:
        """Return empty KPI structure"""
        return {
            'sql_validity_rate': 0.0,
            'correct_answer_rate': 0.0,
            'join_accuracy': 0.0,
            'average_response_time_ms': 0.0,
            'user_satisfaction_score': 0.0,
            'hallucination_frequency': 0.0,
            'total_queries': 0,
            'period_days': 0
        }


# Global instance
evaluation_metrics = EvaluationMetrics()




