"""
Analytical Summary Service - Generate professional narrative summaries
and visualization suggestions from query results
"""
from typing import Dict, Any, List, Optional
import json
import asyncio


class AnalyticalSummaryService:
    """
    Service for generating analytical summaries and visualization suggestions.
    """
    
    @staticmethod
    async def generate_summary(
        results: List[Dict[str, Any]],
        sql_query: str,
        natural_language_query: str
    ) -> str:
        """
        Generate a high-level professional narrative summary of the query results.
        
        Args:
            results: Query results as list of dictionaries
            sql_query: The SQL query that generated these results
            natural_language_query: Original user question
        
        Returns:
            Professional narrative summary
        """
        if not results:
            return f"Query executed successfully but returned no results for: {natural_language_query}"
        
        num_rows = len(results)
        
        # Analyze result structure
        if num_rows == 1:
            # Single row result - describe it
            row = results[0]
            summary = f"Analysis shows: "
            key_value_pairs = []
            for key, value in row.items():
                if key.lower() not in ['id', 'created_at', 'updated_at']:
                    key_value_pairs.append(f"{key.replace('_', ' ').title()}: {value}")
            
            if key_value_pairs:
                summary += ", ".join(key_value_pairs[:5])  # Limit to 5 key fields
            else:
                summary += f"Returned {num_rows} result"
        
        elif num_rows <= 10:
            # Small result set - summarize key patterns
            summary = f"Query returned {num_rows} records. "
            
            # Try to identify key metrics
            first_row = results[0]
            numeric_cols = []
            categorical_cols = []
            
            for key, value in first_row.items():
                if isinstance(value, (int, float)) and value is not None:
                    numeric_cols.append(key)
                elif isinstance(value, str) and len(str(value)) < 50:
                    categorical_cols.append(key)
            
            if numeric_cols:
                # Calculate aggregates if possible
                col = numeric_cols[0]
                values = [r.get(col, 0) for r in results if r.get(col) is not None]
                if values:
                    total = sum(values)
                    avg = total / len(values) if values else 0
                    summary += f"Total {col.replace('_', ' ')}: {total:,.0f}, Average: {avg:,.2f}. "
            
            if categorical_cols:
                col = categorical_cols[0]
                unique_values = set(r.get(col) for r in results if r.get(col))
                if len(unique_values) <= 5:
                    summary += f"Key categories: {', '.join(str(v) for v in list(unique_values)[:5])}. "
        
        else:
            # Large result set - aggregate summary
            summary = f"Query returned {num_rows:,} records. "
            
            # Identify primary metric column
            first_row = results[0]
            metric_cols = [k for k, v in first_row.items() 
                          if isinstance(v, (int, float)) and 'count' in k.lower() or 'total' in k.lower()]
            
            if metric_cols:
                col = metric_cols[0]
                values = [r.get(col, 0) for r in results if r.get(col) is not None]
                if values:
                    total = sum(values)
                    summary += f"Total {col.replace('_', ' ')}: {total:,.0f}. "
        
        # Add context from query
        query_lower = natural_language_query.lower()
        if 'state' in query_lower or 'region' in query_lower:
            summary += "Results are aggregated by geographic region. "
        if 'month' in query_lower or 'year' in query_lower or 'date' in query_lower:
            summary += "Results include temporal analysis. "
        if 'provider' in query_lower or 'facility' in query_lower:
            summary += "Results are organized by healthcare provider. "
        
        # For conversational responses, enhance with LLM if available
        if len(results) > 0 and len(results) <= 20:
            # Try to generate a more conversational summary using LLM
            try:
                conversational_summary = await AnalyticalSummaryService._generate_conversational_summary(
                    results, natural_language_query
                )
                if conversational_summary:
                    summary = conversational_summary
            except Exception as e:
                # Fallback to basic summary if LLM fails
                pass
        
        return summary
    
    @staticmethod
    async def _generate_conversational_summary(
        results: List[Dict[str, Any]],
        natural_language_query: str
    ) -> Optional[str]:
        """Generate a conversational, natural language summary using LLM"""
        try:
            from app.services.ollama_client import get_ollama_client
            
            # Format results for LLM
            results_text = json.dumps(results[:20], indent=2)  # Limit to 20 rows
            
            prompt = f"""You are a data analyst assistant. The user asked: "{natural_language_query}"

The query returned the following results:
{results_text}

Generate a conversational, natural language summary (2-4 sentences) that:
1. Answers the user's question directly
2. Highlights key insights and patterns
3. Mentions specific numbers and trends
4. Uses a friendly, professional tone

Example format:
"Based on the data, [answer to question]. The analysis shows [key insight]. Notably, [interesting pattern or trend]."

Return ONLY the summary text, no markdown, no explanations."""

            ollama_client = await get_ollama_client()
            response = await ollama_client.chat(
                messages=[
                    {"role": "system", "content": "You are a helpful data analyst assistant that provides clear, conversational summaries of data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            if response and len(response.strip()) > 0:
                return response.strip()
        except Exception as e:
            print(f"[WARNING] Failed to generate conversational summary: {e}")
        
        return None
    
    @staticmethod
    def suggest_visualization(
        results: List[Dict[str, Any]],
        sql_query: str
    ) -> Dict[str, Any]:
        """
        Suggest the best chart type based on data shape and structure.
        
        Args:
            results: Query results
            sql_query: The SQL query
        
        Returns:
            Dictionary with visualization suggestion
        """
        if not results:
            return {
                "type": "table",
                "reason": "No data to visualize"
            }
        
        num_rows = len(results)
        first_row = results[0]
        columns = list(first_row.keys())
        
        # Analyze data structure
        numeric_cols = [c for c in columns if isinstance(first_row.get(c), (int, float))]
        categorical_cols = [c for c in columns if isinstance(first_row.get(c), str) and len(str(first_row.get(c))) < 50]
        date_cols = [c for c in columns if 'date' in c.lower() or 'time' in c.lower() or 'created' in c.lower()]
        
        # Decision logic for chart type
        sql_upper = sql_query.upper()
        
        # Time series detection
        if date_cols or 'DATE' in sql_upper or 'MONTH' in sql_upper or 'YEAR' in sql_upper:
            if num_rows > 1 and numeric_cols:
                return {
                    "type": "line",
                    "x_axis": date_cols[0] if date_cols else columns[0],
                    "y_axis": numeric_cols[0],
                    "reason": "Time series data detected - line chart recommended"
                }
        
        # Comparison/ranking
        if categorical_cols and numeric_cols:
            if num_rows <= 20:
                return {
                    "type": "bar",
                    "x_axis": categorical_cols[0],
                    "y_axis": numeric_cols[0],
                    "orientation": "vertical",
                    "reason": "Categorical comparison with numeric values - bar chart recommended"
                }
            else:
                return {
                    "type": "bar",
                    "x_axis": categorical_cols[0],
                    "y_axis": numeric_cols[0],
                    "orientation": "horizontal",
                    "reason": "Many categories - horizontal bar chart recommended"
                }
        
        # Heatmap for two categorical + one numeric
        if len(categorical_cols) >= 2 and numeric_cols:
            if num_rows <= 100:
                return {
                    "type": "heatmap",
                    "x_axis": categorical_cols[0],
                    "y_axis": categorical_cols[1],
                    "value": numeric_cols[0],
                    "reason": "Two categorical dimensions with numeric values - heatmap recommended"
                }
        
        # Pie chart for single categorical + single numeric (small dataset)
        if len(categorical_cols) == 1 and len(numeric_cols) == 1 and num_rows <= 10:
            return {
                "type": "pie",
                "category": categorical_cols[0],
                "value": numeric_cols[0],
                "reason": "Small categorical distribution - pie chart recommended"
            }
        
        # Scatter plot for two numeric columns
        if len(numeric_cols) >= 2:
            return {
                "type": "scatter",
                "x_axis": numeric_cols[0],
                "y_axis": numeric_cols[1],
                "reason": "Two numeric variables - scatter plot recommended"
            }
        
        # Default to table
        return {
            "type": "table",
            "columns": columns,
            "reason": "Complex data structure - table view recommended"
        }


# Global instance
analytical_summary_service = AnalyticalSummaryService()

