"""
Domain 3.4: Feedback Loop & Learning Signals
Continuously improve accuracy using real usage
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pathlib import Path


class FeedbackLearning:
    """
    Answer Feedback Capture, Query Correction Memory, and Golden Question Set
    """
    
    def __init__(self):
        self._feedback_dir = Path(__file__).parent.parent.parent / "data" / "feedback"
        self._feedback_dir.mkdir(parents=True, exist_ok=True)
        self._feedback_file = self._feedback_dir / "feedback_data.json"
        self._corrections_file = self._feedback_dir / "query_corrections.json"
        self._golden_questions_file = self._feedback_dir / "golden_questions.json"
    
    def capture_feedback(self, session_id: str, query: str, sql: str, 
                        feedback_type: str, feedback_data: Dict[str, Any]) -> bool:
        """
        Capture user feedback on query results
        
        Args:
            session_id: Session identifier
            query: Original query
            sql: Generated SQL
            feedback_type: 'positive', 'negative', 'wrong_data', 'wrong_logic', 'incomplete'
            feedback_data: Additional feedback data
        
        Returns:
            True if feedback saved successfully
        """
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'query': query,
            'sql': sql,
            'feedback_type': feedback_type,
            'feedback_data': feedback_data
        }
        
        # Load existing feedback
        feedback_list = []
        if self._feedback_file.exists():
            try:
                with open(self._feedback_file, 'r') as f:
                    feedback_list = json.load(f)
            except:
                feedback_list = []
        
        # Add new feedback
        feedback_list.append(feedback_entry)
        
        # Save
        try:
            with open(self._feedback_file, 'w') as f:
                json.dump(feedback_list, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving feedback: {e}")
            return False
    
    def store_query_correction(self, original_query: str, original_sql: str,
                              corrected_sql: str, correction_reason: str) -> bool:
        """
        Store query correction for future learning
        
        Args:
            original_query: Original natural language query
            original_sql: SQL that failed or was incorrect
            corrected_sql: Corrected SQL
            correction_reason: Why the correction was needed
        
        Returns:
            True if correction saved successfully
        """
        correction_entry = {
            'timestamp': datetime.now().isoformat(),
            'original_query': original_query,
            'original_sql': original_sql,
            'corrected_sql': corrected_sql,
            'correction_reason': correction_reason
        }
        
        # Load existing corrections
        corrections_list = []
        if self._corrections_file.exists():
            try:
                with open(self._corrections_file, 'r') as f:
                    corrections_list = json.load(f)
            except:
                corrections_list = []
        
        # Add new correction
        corrections_list.append(correction_entry)
        
        # Save
        try:
            with open(self._corrections_file, 'w') as f:
                json.dump(corrections_list, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving correction: {e}")
            return False
    
    def get_corrections_for_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Get stored corrections for similar queries
        
        Returns:
            List of correction entries
        """
        if not self._corrections_file.exists():
            return []
        
        try:
            with open(self._corrections_file, 'r') as f:
                corrections_list = json.load(f)
            
            # Simple similarity check (in production, use semantic similarity)
            query_lower = query.lower()
            similar_corrections = []
            
            for correction in corrections_list:
                original_query = correction.get('original_query', '').lower()
                # Check if queries share common keywords
                query_words = set(query_lower.split())
                original_words = set(original_query.split())
                if len(query_words & original_words) >= 2:  # At least 2 common words
                    similar_corrections.append(correction)
            
            return similar_corrections
        except Exception as e:
            print(f"Error loading corrections: {e}")
            return []
    
    def add_golden_question(self, question: str, sql: str, category: str,
                           validated_by: str) -> bool:
        """
        Add question to golden question set
        
        Args:
            question: Natural language question
            sql: Validated SQL
            category: Category (e.g., 'operational', 'regulatory', 'executive')
            validated_by: Who validated this question
        
        Returns:
            True if added successfully
        """
        golden_entry = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'sql': sql,
            'category': category,
            'validated_by': validated_by
        }
        
        # Load existing golden questions
        golden_list = []
        if self._golden_questions_file.exists():
            try:
                with open(self._golden_questions_file, 'r') as f:
                    golden_list = json.load(f)
            except:
                golden_list = []
        
        # Add new golden question
        golden_list.append(golden_entry)
        
        # Save
        try:
            with open(self._golden_questions_file, 'w') as f:
                json.dump(golden_list, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving golden question: {e}")
            return False
    
    def get_golden_questions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get golden question set
        
        Args:
            category: Optional category filter
        
        Returns:
            List of golden questions
        """
        if not self._golden_questions_file.exists():
            return []
        
        try:
            with open(self._golden_questions_file, 'r') as f:
                golden_list = json.load(f)
            
            if category:
                return [q for q in golden_list if q.get('category') == category]
            
            return golden_list
        except Exception as e:
            print(f"Error loading golden questions: {e}")
            return []


# Global instance
feedback_learning = FeedbackLearning()




