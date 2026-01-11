"""
Phase 2: Intent Classifier for Clinical Claims & Diagnosis Domain
Maps natural language questions to canonical intents
"""
from typing import Literal, Dict, Any, Optional
import re


class IntentClassifier:
    """
    Classifies queries into Phase 2 canonical intents:
    - FREQUENCY_VOLUME
    - TREND_TIME_SERIES
    - COST_FINANCIAL
    - SERVICE_UTILIZATION
    """
    
    # Intent patterns
    FREQUENCY_PATTERNS = [
        r'\bmost common\b',
        r'\btop \d+\b',
        r'\bhighest number\b',
        r'\bmost frequent\b',
        r'\bmost often\b',
        r'\bnumber of\b',
        r'\bcount of\b',
        r'\bhow many\b',
        r'\bfrequency\b',
        r'\bvolume\b'
    ]
    
    TREND_PATTERNS = [
        r'\btrend\b',
        r'\bover time\b',
        r'\bmonthly\b',
        r'\byearly\b',
        r'\bquarterly\b',
        r'\bincrease\b',
        r'\bdecrease\b',
        r'\bchange\b',
        r'\bpattern\b',
        r'\bevolution\b'
    ]
    
    COST_PATTERNS = [
        r'\bcost\b',
        r'\bprice\b',
        r'\bexpense\b',
        r'\bexpensive\b',
        r'\bcheap\b',
        r'\baffordable\b',
        r'\bfinancial\b',
        r'\bamount\b',
        r'\btotal cost\b',
        r'\baverage cost\b',
        r'\bper diagnosis\b'
    ]
    
    SERVICE_PATTERNS = [
        r'\bservice\b',
        r'\bservices\b',
        r'\btreatment\b',
        r'\bprocedure\b',
        r'\bused for\b',
        r'\bperformed\b',
        r'\bprovided\b',
        r'\butilization\b'
    ]
    
    def classify_intent(self, query: str) -> Literal["FREQUENCY_VOLUME", "TREND_TIME_SERIES", "COST_FINANCIAL", "SERVICE_UTILIZATION", "UNKNOWN"]:
        """
        Classify query into canonical intent
        
        Args:
            query: Natural language query
            
        Returns:
            Canonical intent type
        """
        query_lower = query.lower()
        
        # Check for service utilization first (most specific)
        if any(re.search(pattern, query_lower) for pattern in self.SERVICE_PATTERNS):
            return "SERVICE_UTILIZATION"
        
        # Check for cost/financial
        if any(re.search(pattern, query_lower) for pattern in self.COST_PATTERNS):
            return "COST_FINANCIAL"
        
        # Check for trend/time series
        if any(re.search(pattern, query_lower) for pattern in self.TREND_PATTERNS):
            return "TREND_TIME_SERIES"
        
        # Check for frequency/volume (default for most queries)
        if any(re.search(pattern, query_lower) for pattern in self.FREQUENCY_PATTERNS):
            return "FREQUENCY_VOLUME"
        
        # Default to frequency/volume for diagnosis queries
        if 'diagnosis' in query_lower or 'disease' in query_lower:
            return "FREQUENCY_VOLUME"
        
        return "UNKNOWN"
    
    def extract_time_reference(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Extract time reference from query
        
        Returns:
            Dict with 'type' and 'value' or None
        """
        query_lower = query.lower()
        
        # Last year
        if re.search(r'\blast year\b', query_lower):
            return {"type": "last_year", "sql": "YEAR(c.created_at) = YEAR(CURRENT_DATE) - 1"}
        
        # This year
        if re.search(r'\bthis year\b', query_lower):
            return {"type": "this_year", "sql": "YEAR(c.created_at) = YEAR(CURRENT_DATE)"}
        
        # Recent
        if re.search(r'\brecent\b', query_lower):
            return {"type": "recent", "sql": "c.created_at >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)", "needs_clarification": True}
        
        # Last N days
        days_match = re.search(r'\blast (\d+) days?\b', query_lower)
        if days_match:
            days = int(days_match.group(1))
            return {"type": "last_n_days", "sql": f"c.created_at >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"}
        
        # Last N months
        months_match = re.search(r'\blast (\d+) months?\b', query_lower)
        if months_match:
            months = int(months_match.group(1))
            return {"type": "last_n_months", "sql": f"c.created_at >= DATE_SUB(CURDATE(), INTERVAL {months} MONTH)"}
        
        # Specific month/year
        month_year_match = re.search(r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b', query_lower)
        if month_year_match:
            month_name = month_year_match.group(1)
            year = int(month_year_match.group(2))
            month_num = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }[month_name]
            return {"type": "specific_month", "sql": f"YEAR(c.created_at) = {year} AND MONTH(c.created_at) = {month_num}"}
        
        return None
    
    def extract_top_n(self, query: str) -> Optional[int]:
        """
        Extract "top N" value from query
        
        Returns:
            Number or None
        """
        query_lower = query.lower()
        
        # Top N
        top_match = re.search(r'\btop (\d+)\b', query_lower)
        if top_match:
            return int(top_match.group(1))
        
        # Most common (default to 1)
        if re.search(r'\bmost common\b', query_lower) or re.search(r'\bhighest\b', query_lower):
            return 1
        
        return None
    
    def needs_clarification(self, query: str, intent: str) -> Optional[str]:
        """
        Check if query needs clarification
        
        Returns:
            Clarification question or None
        """
        query_lower = query.lower()
        
        # Cost ambiguity
        if intent == "COST_FINANCIAL" and re.search(r'\bcost\b', query_lower) and not re.search(r'\b(total|average|avg|sum)\b', query_lower):
            return "Do you want the total cost or average cost per diagnosis?"
        
        # Recent ambiguity
        if re.search(r'\brecent\b', query_lower):
            return "What timeframe do you mean by 'recent'? (e.g., last 30 days, last 3 months)"
        
        # Top N ambiguity
        if intent == "FREQUENCY_VOLUME" and re.search(r'\btop\b', query_lower) and not re.search(r'\btop \d+\b', query_lower):
            return "How many top results do you want? (e.g., top 10, top 5)"
        
        # Cases vs Claims ambiguity
        if re.search(r'\bcases\b', query_lower) and not re.search(r'\b(claims|encounters)\b', query_lower):
            return "Do you mean clinical cases (encounters) or administrative claims?"
        
        return None


# Global instance
intent_classifier = IntentClassifier()




