"""
Insight Generator Service
Converts raw query results into human-readable executive insights
Prevents hallucination by grounding all insights in actual data
"""
from typing import Dict, Any, List, Optional
from app.services.llm_client import llm_client
from app.core.config import settings


class InsightGenerator:
    """
    Generates human-readable insights from query results.
    
    Format: Insight → Evidence → Implication
    
    Rules:
    - Only use actual data from query results
    - Never invent numbers
    - Clearly state when data doesn't exist
    - Provide executive-grade insights, not raw SQL
    """
    
    SYSTEM_PROMPT = """You are an Executive Healthcare Intelligence Assistant. Your role is to convert raw database query results into clear, actionable insights for healthcare administrators, NHIS regulators, and finance auditors.

CRITICAL RULES (MUST FOLLOW):

1. GROUNDED RESPONSES ONLY:
   - Use ONLY the data provided in the query results
   - Never invent, estimate, or extrapolate numbers not in the results
   - If a number isn't in the results, don't mention it

2. RESPONSE STRUCTURE:
   Format your response as:
   - **Insight**: Clear, executive summary (1-2 sentences)
   - **Evidence**: Key numbers and facts from the data
   - **Implication**: What this means for decision-making (if applicable)

3. NO RAW SQL OR TECHNICAL DETAILS:
   - Never show SQL queries unless explicitly requested
   - Never show raw column names or database jargon
   - Use natural, professional language

4. HANDLE EMPTY RESULTS:
   - If results are empty: "The database does not contain data matching your query criteria."
   - Be specific about what was searched (e.g., "No claims found for Kogi State in 2023")

5. HANDLE SINGLE RESULTS:
   - Provide clear, direct answer
   - Include relevant context and implications

6. HANDLE MULTIPLE RESULTS:
   - Summarize key patterns
   - Highlight top/bottom values if relevant
   - Provide meaningful aggregations or trends

7. PROFESSIONAL TONE:
   - Executive-level language
   - Clear and concise
   - Actionable insights
   - No jargon or technical terms

8. GEOGRAPHY HANDLING:
   - Use full state names (e.g., "Kogi State" not "Kogi")
   - Reference regions/zones when relevant

9. TIME HANDLING:
   - Use clear date ranges
   - Reference time periods naturally (e.g., "in 2023", "this month")

10. PERCENTAGES AND COMPARISONS:
    - Calculate percentages only from provided data
    - Make comparisons only when data supports them
    - Use phrases like "X% of total" only when total is in results

EXAMPLE OUTPUT:

Query: "How many claims are in Kogi State?"
Results: [{"state": "Kogi", "count": 12402}]

Response:
"Kogi State has 12,402 healthcare claims in the database. This represents a significant volume of healthcare activity, indicating strong utilization of healthcare services in the state."

Query: "Top diseases by claim count"
Results: [{"disease": "Malaria", "count": 8500}, {"disease": "Typhoid", "count": 3200}]

Response:
"Malaria is the leading diagnosis with 8,500 claims, followed by Typhoid with 3,200 claims. Malaria accounts for 72% of the top two diagnoses, highlighting the need for focused malaria prevention and treatment programs."

Query: "Claims by status"
Results: [{"status": "Approved", "count": 5000}, {"status": "Pending", "count": 2000}]

Response:
"Of the claims in the system, 5,000 are approved and 2,000 are pending approval. The approval rate is 71%, indicating a healthy processing pipeline with room for improvement in pending claim resolution."

Remember: Be accurate, grounded, and executive-focused. Never hallucinate."""

    def __init__(self):
        self.max_results_for_insight = 100  # Limit results used for insight generation
    
    async def generate_insight(
        self,
        query: str,
        results: List[Dict[str, Any]],
        sql: Optional[str] = None,
        row_count: Optional[int] = None
    ) -> str:
        """
        Generate human-readable insight from query results.
        
        Args:
            query: Original user query
            results: Query results (list of dicts)
            sql: SQL query used (optional, for context)
            row_count: Total number of rows (optional)
        
        Returns:
            Human-readable insight string
        """
        # Handle empty results
        if not results or len(results) == 0:
            return self._generate_empty_result_insight(query)
        
        # Limit results to avoid token limits
        results_for_insight = results[:self.max_results_for_insight]
        total_count = row_count if row_count is not None else len(results)
        
        # Build prompt with results
        results_text = self._format_results_for_prompt(results_for_insight, total_count)
        
        user_prompt = f"""User Query: {query}

Query Results:
{results_text}

Generate a clear, executive-level insight based on these results. Follow the format: Insight → Evidence → Implication."""

        try:
            # Generate insight using LLM
            insight = await llm_client.generate(
                prompt=f"{self.SYSTEM_PROMPT}\n\n{user_prompt}",
                temperature=0.3,  # Low temperature for accuracy
                max_tokens=500
            )
            
            return insight.strip()
        
        except Exception as e:
            print(f"⚠️  Insight generation error: {e}")
            # Fallback to simple summary
            return self._generate_fallback_insight(query, results, total_count)
    
    def _format_results_for_prompt(self, results: List[Dict[str, Any]], total_count: int) -> str:
        """Format query results for LLM prompt"""
        if not results:
            return "No results found."
        
        # Format as readable text
        lines = []
        lines.append(f"Total rows: {total_count}")
        lines.append(f"Showing: {len(results)} rows")
        lines.append("")
        lines.append("Data:")
        
        # Show first few rows as examples
        for i, row in enumerate(results[:20], 1):  # Limit to 20 rows for prompt
            row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
            lines.append(f"  Row {i}: {row_str}")
        
        if len(results) > 20:
            lines.append(f"  ... and {len(results) - 20} more rows")
        
        return "\n".join(lines)
    
    def _generate_empty_result_insight(self, query: str) -> str:
        """Generate insight for empty results"""
        return (
            f"The database does not contain data matching your query: '{query}'. "
            "This could mean the data doesn't exist for the specified criteria, or the query parameters need adjustment."
        )
    
    def _generate_fallback_insight(self, query: str, results: List[Dict[str, Any]], total_count: int) -> str:
        """Generate simple fallback insight when LLM fails"""
        if not results:
            return self._generate_empty_result_insight(query)
        
        # Simple summary
        result_count = len(results)
        if result_count == 1:
            row = results[0]
            key_values = ", ".join([f"{k}: {v}" for k, v in list(row.items())[:3]])
            return f"Query returned 1 result: {key_values}."
        else:
            return (
                f"Query returned {total_count} results. "
                f"Key data points: {self._extract_key_summary(results)}"
            )
    
    def _extract_key_summary(self, results: List[Dict[str, Any]]) -> str:
        """Extract key summary from results for fallback"""
        if not results:
            return "No data"
        
        # Try to find numeric columns and summarize
        summary_parts = []
        
        # Look for common patterns
        for row in results[:5]:  # Check first 5 rows
            for key, value in row.items():
                if isinstance(value, (int, float)) and value > 0:
                    if key.lower() not in ['id', 'user_id', 'claim_id']:
                        summary_parts.append(f"{key}: {value}")
                        break
        
        if summary_parts:
            return "; ".join(summary_parts[:3])
        
        return f"{len(results)} records found"


# Global instance
insight_generator = InsightGenerator()
