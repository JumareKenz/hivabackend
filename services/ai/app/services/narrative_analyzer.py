"""
Narrative Analyzer - Provides insights and analysis of query results
Used for follow-up questions like "tell me more about it"
Enhanced with robust error handling and timeout management
"""
from typing import Dict, Any, List, Optional
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class NarrativeAnalyzer:
    """
    Analyzes query results and provides narrative insights.
    Used when user asks for interpretation/analysis of existing data.
    """
    
    async def analyze_results(
        self,
        results: List[Dict[str, Any]],
        original_query: str,
        sql_query: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate narrative analysis of query results.
        
        Args:
            results: The query results to analyze
            original_query: The original user query that generated these results
            sql_query: The SQL query that was executed
            conversation_context: Previous conversation messages
        
        Returns:
            Dict with:
                - narrative: str (main narrative summary)
                - insights: List[str] (key insights)
                - suggestions: List[str] (suggested follow-up questions)
                - statistics: Dict (key statistics)
        """
        if not results:
            return {
                "narrative": "The query returned no results. This could mean there's no data matching your criteria, or the query needs to be adjusted.",
                "insights": [],
                "suggestions": [
                    "Try adjusting the date range or filters",
                    "Check if the data exists for the specified criteria"
                ],
                "statistics": {}
            }
        
        # Extract statistics
        statistics = self._extract_statistics(results)
        
        # Generate narrative using LLM
        narrative = await self._generate_narrative(
            results, 
            original_query, 
            sql_query,
            statistics,
            conversation_context
        )
        
        # Extract insights
        insights = self._extract_insights(results, statistics)
        
        # Generate suggestions
        suggestions = self._generate_suggestions(original_query, results, statistics)
        
        return {
            "narrative": narrative,
            "insights": insights,
            "suggestions": suggestions,
            "statistics": statistics
        }
    
    def _extract_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract key statistics from results"""
        if not results:
            return {}
        
        stats = {
            "row_count": len(results),
            "columns": list(results[0].keys()) if results else []
        }
        
        # Find numeric columns
        first_row = results[0]
        numeric_cols = []
        categorical_cols = []
        
        for key, value in first_row.items():
            if isinstance(value, (int, float)) and value is not None:
                numeric_cols.append(key)
                # Calculate aggregates
                values = [r.get(key, 0) for r in results if r.get(key) is not None]
                if values:
                    stats[f"{key}_total"] = sum(values)
                    stats[f"{key}_average"] = sum(values) / len(values) if values else 0
                    stats[f"{key}_min"] = min(values)
                    stats[f"{key}_max"] = max(values)
            elif isinstance(value, str) and len(str(value)) < 100:
                categorical_cols.append(key)
        
        stats["numeric_columns"] = numeric_cols
        stats["categorical_columns"] = categorical_cols
        
        # Count unique values for categorical columns
        for col in categorical_cols[:3]:  # Limit to first 3
            unique_values = set(r.get(col) for r in results if r.get(col))
            stats[f"{col}_unique_count"] = len(unique_values)
            if len(unique_values) <= 10:
                stats[f"{col}_values"] = list(unique_values)
        
        return stats
    
    def _extract_insights(
        self, 
        results: List[Dict[str, Any]], 
        statistics: Dict[str, Any]
    ) -> List[str]:
        """Extract key insights from results"""
        insights = []
        
        if statistics.get("row_count", 0) == 0:
            return ["No data found matching the query criteria"]
        
        # Insight about volume
        row_count = statistics.get("row_count", 0)
        if row_count > 0:
            insights.append(f"Query returned {row_count:,} result{'s' if row_count != 1 else ''}")
        
        # Insight about numeric trends
        for col in statistics.get("numeric_columns", [])[:2]:
            total = statistics.get(f"{col}_total")
            avg = statistics.get(f"{col}_average")
            if total is not None and avg is not None:
                insights.append(f"Total {col.replace('_', ' ')}: {total:,.0f}, Average: {avg:,.2f}")
        
        # Insight about distribution
        for col in statistics.get("categorical_columns", [])[:1]:
            unique_count = statistics.get(f"{col}_unique_count", 0)
            if unique_count > 0:
                insights.append(f"Data spans {unique_count} unique {col.replace('_', ' ')}")
        
        return insights
    
    def _generate_suggestions(
        self,
        original_query: str,
        results: List[Dict[str, Any]],
        statistics: Dict[str, Any]
    ) -> List[str]:
        """Generate suggested follow-up questions"""
        suggestions = []
        query_lower = original_query.lower()
        
        # Time-based suggestions
        if any(word in query_lower for word in ['month', 'year', 'date', 'april', 'may', 'june']):
            suggestions.append("Compare with previous months or other time periods")
        
        # State/region suggestions
        if any(word in query_lower for word in ['state', 'zamfara', 'kogi', 'region']):
            suggestions.append("Compare with other states or regions")
            suggestions.append("See breakdown by local government area")
        
        # Volume/count suggestions
        if 'count' in query_lower or 'number' in query_lower or 'total' in query_lower:
            suggestions.append("See breakdown by category or type")
            suggestions.append("Analyze trends over time")
        
        # Generic suggestions
        if statistics.get("numeric_columns"):
            suggestions.append("View detailed breakdown by key dimensions")
        
        if not suggestions:
            suggestions.append("Explore related data or time periods")
            suggestions.append("Compare with other metrics or dimensions")
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    async def _generate_narrative(
        self,
        results: List[Dict[str, Any]],
        original_query: str,
        sql_query: Optional[str],
        statistics: Dict[str, Any],
        conversation_context: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Generate natural language narrative using LLM"""
        try:
            from app.services.ollama_client import get_ollama_client
            
            # Prepare results summary (limit to avoid token overflow)
            results_sample = results[:10]  # First 10 rows
            results_summary = json.dumps(results_sample, indent=2, default=str)
            
            # Build context
            context_parts = []
            if conversation_context:
                recent_queries = [msg.get("content", "") for msg in conversation_context[-4:] if msg.get("role") == "user"]
                if recent_queries:
                    context_parts.append(f"Recent conversation: {'; '.join(recent_queries[-2:])}")
            
            context_str = "\n".join(context_parts) if context_parts else "No previous context"
            
            # Build statistics summary
            stats_summary = f"""
- Total rows: {statistics.get('row_count', 0):,}
- Numeric columns: {', '.join(statistics.get('numeric_columns', [])[:3])}
- Key metrics: {json.dumps({k: v for k, v in statistics.items() if '_total' in k or '_average' in k}, default=str)}
"""
            
            prompt = f"""You are a senior data analyst. The user asked: "{original_query}"

The query returned these results (sample):
{results_summary}

Key Statistics:
{stats_summary}

Context: {context_str}

Generate a comprehensive, conversational narrative analysis (3-5 sentences) that:
1. Directly answers what the data shows
2. Highlights key patterns, trends, or anomalies
3. Provides context and interpretation
4. Uses specific numbers from the data
5. Writes in a friendly, professional tone

Example format:
"Based on the data, [direct answer]. The analysis reveals [key pattern]. Notably, [interesting finding]. This represents [context/interpretation]. [Additional insight]."

Return ONLY the narrative text, no markdown, no bullet points, just flowing prose."""

            ollama_client = await get_ollama_client()
            response = await asyncio.wait_for(
                ollama_client.chat(
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are a senior data analyst who provides clear, insightful narrative summaries of data. "
                                     "Write in a warm, professional, and conversational tone."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=400
                ),
                timeout=12.0  # Increased timeout slightly
            )
            
            if response and len(response.strip()) > 0:
                logger.debug(f"Narrative generated successfully: {len(response)} characters")
                return response.strip()
            else:
                logger.warning("Empty narrative response from LLM")
        except asyncio.TimeoutError:
            logger.warning("Narrative generation timed out, using fallback")
        except Exception as e:
            logger.warning(f"Narrative generation failed: {e}", exc_info=True)
        
        # Fallback to basic narrative
        logger.info("Using fallback narrative generation")
        return self._generate_fallback_narrative(results, statistics)
    
    def _generate_fallback_narrative(
        self,
        results: List[Dict[str, Any]],
        statistics: Dict[str, Any]
    ) -> str:
        """Generate basic narrative without LLM"""
        row_count = statistics.get("row_count", 0)
        
        narrative_parts = [f"The query returned {row_count:,} result{'s' if row_count != 1 else ''}."]
        
        # Add numeric insights
        for col in statistics.get("numeric_columns", [])[:2]:
            total = statistics.get(f"{col}_total")
            avg = statistics.get(f"{col}_average")
            if total is not None:
                narrative_parts.append(f"The total {col.replace('_', ' ')} is {total:,.0f}")
                if avg is not None:
                    narrative_parts.append(f"with an average of {avg:,.2f}")
        
        return " ".join(narrative_parts) + " For more detailed insights, try asking specific follow-up questions."


# Global instance
narrative_analyzer = NarrativeAnalyzer()

