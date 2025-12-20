"""
Visualization Service - Generates charts and formatted tables from query results
"""
from typing import List, Dict, Any, Optional
import json


class VisualizationService:
    """Generates visualizations and formatted output from SQL query results"""
    
    def analyze_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze query results and suggest appropriate visualization
        
        Args:
            data: List of dictionaries representing query results
        
        Returns:
            Dictionary with visualization suggestions and formatted data
        """
        if not data:
            return {
                "type": "empty",
                "message": "No data returned from query",
                "data": []
            }
        
        # Get column names
        columns = list(data[0].keys()) if data else []
        
        # Determine visualization type based on data structure
        num_rows = len(data)
        num_cols = len(columns)
        
        # Check for numeric columns
        numeric_cols = []
        for col in columns:
            try:
                # Check if column contains numeric data
                sample_values = [row.get(col) for row in data[:10] if row.get(col) is not None]
                if sample_values:
                    float(sample_values[0])
                    numeric_cols.append(col)
            except (ValueError, TypeError):
                pass
        
        # Determine best visualization type
        viz_type = "table"  # Default
        
        if num_rows == 1:
            # Single row - show as key-value pairs or metric cards
            viz_type = "metrics"
        elif num_cols == 2 and len(numeric_cols) == 1:
            # Two columns, one numeric - bar or line chart
            viz_type = "bar_chart"
        elif num_cols >= 2 and len(numeric_cols) >= 1:
            # Multiple columns with numeric data - table with charts
            viz_type = "table_with_chart"
        elif num_rows <= 20:
            # Small dataset - simple table
            viz_type = "table"
        else:
            # Large dataset - paginated table
            viz_type = "paginated_table"
        
        return {
            "type": viz_type,
            "row_count": num_rows,
            "columns": columns,
            "numeric_columns": numeric_cols,
            "data": data,
            "suggestions": self._get_viz_suggestions(viz_type, columns, numeric_cols)
        }
    
    def _get_viz_suggestions(
        self,
        viz_type: str,
        columns: List[str],
        numeric_cols: List[str]
    ) -> List[str]:
        """Get visualization suggestions based on data type"""
        suggestions = []
        
        if viz_type == "bar_chart":
            suggestions.append("This data is suitable for a bar chart")
            if numeric_cols:
                suggestions.append(f"Use '{numeric_cols[0]}' as the value axis")
        elif viz_type == "table_with_chart":
            suggestions.append("Consider a bar or line chart for trends")
            if len(numeric_cols) > 1:
                suggestions.append("Multiple metrics can be compared side-by-side")
        elif viz_type == "metrics":
            suggestions.append("Display as metric cards or key-value pairs")
        
        return suggestions
    
    def format_table(
        self,
        data: List[Dict[str, Any]],
        max_rows: int = 100
    ) -> Dict[str, Any]:
        """
        Format data as a table with pagination support
        
        Args:
            data: Query results
            max_rows: Maximum rows to return in one page
        
        Returns:
            Formatted table data
        """
        if not data:
            return {
                "rows": [],
                "columns": [],
                "total_rows": 0,
                "page": 1,
                "page_size": max_rows,
                "has_more": False
            }
        
        columns = list(data[0].keys())
        total_rows = len(data)
        
        # Paginate if needed
        paginated_data = data[:max_rows]
        has_more = total_rows > max_rows
        
        # Format data (handle None, dates, numbers)
        formatted_rows = []
        for row in paginated_data:
            formatted_row = {}
            for col in columns:
                value = row.get(col)
                # Format based on type
                if value is None:
                    formatted_row[col] = None
                elif isinstance(value, (int, float)):
                    formatted_row[col] = value
                else:
                    formatted_row[col] = str(value)
            formatted_rows.append(formatted_row)
        
        return {
            "rows": formatted_rows,
            "columns": columns,
            "total_rows": total_rows,
            "page": 1,
            "page_size": max_rows,
            "has_more": has_more,
            "display_count": len(paginated_data)
        }
    
    def generate_summary(
        self,
        data: List[Dict[str, Any]],
        query_explanation: str
    ) -> str:
        """
        Generate a natural language summary of the query results
        
        Args:
            data: Query results
            query_explanation: Explanation of what the query does
        
        Returns:
            Natural language summary
        """
        if not data:
            return f"The query returned no results. {query_explanation}"
        
        num_rows = len(data)
        
        # Get sample of data for summary
        sample = data[:5]
        
        summary = f"Query returned {num_rows} result{'s' if num_rows != 1 else ''}. "
        summary += f"{query_explanation}\n\n"
        
        if num_rows <= 10:
            summary += "All results are shown below."
        else:
            summary += f"Showing first {len(sample)} of {num_rows} results."
        
        return summary


# Global instance
visualization_service = VisualizationService()



