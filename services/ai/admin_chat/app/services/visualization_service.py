"""
Visualization Service - Generates charts, graphs, and formatted tables from query results
Supports:
- Chart configuration objects (Plotly, Chart.js)
- Chart image generation (PNG/SVG)
- Enhanced metadata (axis labels, colors, chart settings)
"""
from typing import List, Dict, Any, Optional
import json
import base64
import io
from datetime import datetime

# Optional imports for chart generation
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class VisualizationService:
    """Generates visualizations, chart configs, and images from SQL query results"""
    
    # Color palettes for charts
    COLOR_PALETTES = {
        'default': ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'],
        'blue': ['#1E40AF', '#3B82F6', '#60A5FA', '#93C5FD', '#DBEAFE'],
        'green': ['#065F46', '#10B981', '#34D399', '#6EE7B7', '#A7F3D0'],
        'warm': ['#DC2626', '#EA580C', '#F59E0B', '#EAB308', '#84CC16'],
    }
    
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
        categorical_cols = []
        for col in columns:
            try:
                # Check if column contains numeric data
                sample_values = [row.get(col) for row in data[:10] if row.get(col) is not None]
                if sample_values:
                    # Try to convert first non-None value to float
                    test_value = sample_values[0]
                    if test_value is not None:
                        try:
                            float(test_value)
                            numeric_cols.append(col)
                        except (ValueError, TypeError):
                            categorical_cols.append(col)
                    else:
                        categorical_cols.append(col)
                else:
                    categorical_cols.append(col)
            except (ValueError, TypeError, AttributeError):
                categorical_cols.append(col)
        
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
        
        # Generate chart configurations and images
        chart_configs = self._generate_chart_configs(data, viz_type, columns, numeric_cols, categorical_cols)
        chart_image = self._generate_chart_image(data, viz_type, columns, numeric_cols, categorical_cols)
        metadata = self._generate_metadata(data, viz_type, columns, numeric_cols, categorical_cols)
        
        return {
            "type": viz_type,
            "row_count": num_rows,
            "columns": columns,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "data": data,
            "suggestions": self._get_viz_suggestions(viz_type, columns, numeric_cols),
            "chart_config": chart_configs,
            "chart_image": chart_image,
            "metadata": metadata
        }
    
    def _generate_chart_configs(
        self,
        data: List[Dict[str, Any]],
        viz_type: str,
        columns: List[str],
        numeric_cols: List[str],
        categorical_cols: List[str]
    ) -> Dict[str, Any]:
        """Generate chart configuration objects for Plotly and Chart.js"""
        configs = {
            "plotly": None,
            "chartjs": None
        }
        
        if not data or viz_type in ["table", "paginated_table", "empty", "metrics"]:
            return configs
        
        try:
            if viz_type == "bar_chart" and len(columns) == 2 and len(numeric_cols) == 1:
                # Extract data for bar chart
                cat_col = categorical_cols[0] if categorical_cols else columns[0]
                num_col = numeric_cols[0]
                
                labels = [str(row.get(cat_col, '') or '') for row in data]
                values = [float(row.get(num_col, 0) or 0) for row in data]
                
                # Generate Plotly config
                if PLOTLY_AVAILABLE:
                    fig = go.Figure(data=[
                        go.Bar(
                            x=labels,
                            y=values,
                            marker_color=self.COLOR_PALETTES['default'][0],
                            text=values,
                            textposition='auto',
                        )
                    ])
                    fig.update_layout(
                        title=f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                        xaxis_title=cat_col.replace('_', ' ').title(),
                        yaxis_title=num_col.replace('_', ' ').title(),
                        template="plotly_white",
                        height=400
                    )
                    configs["plotly"] = json.loads(fig.to_json())
                
                # Generate Chart.js config
                configs["chartjs"] = {
                    "type": "bar",
                    "data": {
                        "labels": labels,
                        "datasets": [{
                            "label": num_col.replace('_', ' ').title(),
                            "data": values,
                            "backgroundColor": self.COLOR_PALETTES['default'][0],
                            "borderColor": self.COLOR_PALETTES['default'][0],
                            "borderWidth": 1
                        }]
                    },
                    "options": {
                        "responsive": True,
                        "plugins": {
                            "title": {
                                "display": True,
                                "text": f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}"
                            },
                            "legend": {
                                "display": True
                            }
                        },
                        "scales": {
                            "y": {
                                "beginAtZero": True,
                                "title": {
                                    "display": True,
                                    "text": num_col.replace('_', ' ').title()
                                }
                            },
                            "x": {
                                "title": {
                                    "display": True,
                                    "text": cat_col.replace('_', ' ').title()
                                }
                            }
                        }
                    }
                }
            
            elif viz_type == "table_with_chart" and len(numeric_cols) >= 1:
                # Multi-series chart
                cat_col = categorical_cols[0] if categorical_cols else columns[0]
                labels = [str(row.get(cat_col, '')) for row in data]
                
                # Generate Plotly config
                if PLOTLY_AVAILABLE:
                    fig = go.Figure()
                    colors = self.COLOR_PALETTES['default']
                    for i, num_col in enumerate(numeric_cols):
                        values = [float(row.get(num_col, 0) or 0) for row in data]
                        fig.add_trace(go.Bar(
                            name=num_col.replace('_', ' ').title(),
                            x=labels,
                            y=values,
                            marker_color=colors[i % len(colors)]
                        ))
                    fig.update_layout(
                        title="Multiple Metrics Comparison",
                        xaxis_title=cat_col.replace('_', ' ').title(),
                        yaxis_title="Value",
                        barmode='group',
                        template="plotly_white",
                        height=400
                    )
                    configs["plotly"] = json.loads(fig.to_json())
                
                # Generate Chart.js config
                datasets = []
                colors = self.COLOR_PALETTES['default']
                for i, num_col in enumerate(numeric_cols):
                    values = [float(row.get(num_col, 0) or 0) for row in data]
                    datasets.append({
                        "label": num_col.replace('_', ' ').title(),
                        "data": values,
                        "backgroundColor": colors[i % len(colors)],
                        "borderColor": colors[i % len(colors)],
                        "borderWidth": 1
                    })
                
                configs["chartjs"] = {
                    "type": "bar",
                    "data": {
                        "labels": labels,
                        "datasets": datasets
                    },
                    "options": {
                        "responsive": True,
                        "plugins": {
                            "title": {
                                "display": True,
                                "text": "Multiple Metrics Comparison"
                            },
                            "legend": {
                                "display": True
                            }
                        },
                        "scales": {
                            "y": {
                                "beginAtZero": True
                            }
                        }
                    }
                }
        except Exception as e:
            print(f"Error generating chart configs: {e}")
        
        return configs
    
    def _generate_chart_image(
        self,
        data: List[Dict[str, Any]],
        viz_type: str,
        columns: List[str],
        numeric_cols: List[str],
        categorical_cols: List[str]
    ) -> Dict[str, Any]:
        """Generate chart as PNG image (base64 encoded)"""
        if not MATPLOTLIB_AVAILABLE or not data or viz_type in ["table", "paginated_table", "empty", "metrics"]:
            return {
                "available": False,
                "format": None,
                "data": None
            }
        
        try:
            if viz_type == "bar_chart" and len(columns) == 2 and len(numeric_cols) == 1:
                cat_col = categorical_cols[0] if categorical_cols else columns[0]
                num_col = numeric_cols[0]
                
                labels = [str(row.get(cat_col, ''))[:20] for row in data]  # Truncate long labels
                values = [float(row.get(num_col, 0)) for row in data]
                
                # Create figure
                plt.figure(figsize=(10, 6))
                bars = plt.bar(range(len(labels)), values, color=self.COLOR_PALETTES['default'][0], alpha=0.8)
                
                # Add value labels on bars
                for i, (bar, val) in enumerate(zip(bars, values)):
                    height = bar.get_height()
                    plt.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(val):,}' if val == int(val) else f'{val:.1f}',
                            ha='center', va='bottom', fontsize=9)
                
                plt.xlabel(cat_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
                plt.ylabel(num_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
                plt.title(f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}", 
                         fontsize=14, fontweight='bold', pad=20)
                plt.xticks(range(len(labels)), labels, rotation=45, ha='right')
                plt.grid(axis='y', alpha=0.3, linestyle='--')
                plt.tight_layout()
                
                # Save to bytes
                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                img_buffer.seek(0)
                img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                plt.close()
                
                return {
                    "available": True,
                    "format": "png",
                    "data": f"data:image/png;base64,{img_base64}",
                    "width": 1000,
                    "height": 600
                }
            
            elif viz_type == "table_with_chart" and len(numeric_cols) >= 1:
                cat_col = categorical_cols[0] if categorical_cols else columns[0]
                labels = [str(row.get(cat_col, ''))[:20] for row in data]
                
                # Create grouped bar chart
                x = range(len(labels))
                width = 0.8 / len(numeric_cols)
                colors = self.COLOR_PALETTES['default']
                
                plt.figure(figsize=(12, 6))
                for i, num_col in enumerate(numeric_cols):
                    values = [float(row.get(num_col, 0) or 0) for row in data]
                    offset = (i - len(numeric_cols)/2 + 0.5) * width
                    plt.bar([xi + offset for xi in x], values, width, 
                           label=num_col.replace('_', ' ').title(),
                           color=colors[i % len(colors)], alpha=0.8)
                
                plt.xlabel(cat_col.replace('_', ' ').title(), fontsize=12, fontweight='bold')
                plt.ylabel("Value", fontsize=12, fontweight='bold')
                plt.title("Multiple Metrics Comparison", fontsize=14, fontweight='bold', pad=20)
                plt.xticks(x, labels, rotation=45, ha='right')
                plt.legend()
                plt.grid(axis='y', alpha=0.3, linestyle='--')
                plt.tight_layout()
                
                # Save to bytes
                img_buffer = io.BytesIO()
                plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
                img_buffer.seek(0)
                img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
                plt.close()
                
                return {
                    "available": True,
                    "format": "png",
                    "data": f"data:image/png;base64,{img_base64}",
                    "width": 1200,
                    "height": 600
                }
        except Exception as e:
            print(f"Error generating chart image: {e}")
            return {
                "available": False,
                "format": None,
                "data": None,
                "error": str(e)
            }
        
        return {
            "available": False,
            "format": None,
            "data": None
        }
    
    def _generate_metadata(
        self,
        data: List[Dict[str, Any]],
        viz_type: str,
        columns: List[str],
        numeric_cols: List[str],
        categorical_cols: List[str]
    ) -> Dict[str, Any]:
        """Generate enhanced metadata (axis labels, colors, chart settings)"""
        metadata = {
            "chart_type": viz_type,
            "axes": {},
            "colors": {},
            "settings": {},
            "data_stats": {}
        }
        
        if not data:
            return metadata
        
        # Generate axis labels
        if viz_type == "bar_chart" and len(columns) == 2:
            cat_col = categorical_cols[0] if categorical_cols else columns[0]
            num_col = numeric_cols[0] if numeric_cols else columns[1]
            
            metadata["axes"] = {
                "x": {
                    "label": cat_col.replace('_', ' ').title(),
                    "column": cat_col,
                    "type": "categorical"
                },
                "y": {
                    "label": num_col.replace('_', ' ').title(),
                    "column": num_col,
                    "type": "numeric"
                }
            }
            
            # Calculate statistics
            values = [float(row.get(num_col, 0) or 0) for row in data]
            metadata["data_stats"] = {
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "sum": sum(values),
                "avg": sum(values) / len(values) if values else 0,
                "count": len(values)
            }
        
        elif viz_type == "table_with_chart" and len(numeric_cols) >= 1:
            cat_col = categorical_cols[0] if categorical_cols else columns[0]
            
            metadata["axes"] = {
                "x": {
                    "label": cat_col.replace('_', ' ').title(),
                    "column": cat_col,
                    "type": "categorical"
                },
                "y": {
                    "label": "Value",
                    "type": "numeric",
                    "columns": numeric_cols
                }
            }
            
            # Calculate statistics for each numeric column
            stats = {}
            for num_col in numeric_cols:
                values = [float(row.get(num_col, 0) or 0) for row in data]
                stats[num_col] = {
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "sum": sum(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "count": len(values)
                }
            metadata["data_stats"] = stats
        
        # Color scheme
        metadata["colors"] = {
            "palette": "default",
            "primary": self.COLOR_PALETTES['default'][0],
            "secondary": self.COLOR_PALETTES['default'][1] if len(self.COLOR_PALETTES['default']) > 1 else None,
            "all": self.COLOR_PALETTES['default']
        }
        
        # Chart settings
        metadata["settings"] = {
            "responsive": True,
            "show_legend": len(numeric_cols) > 1,
            "show_grid": True,
            "show_values": True,
            "rotation": 45 if len(data) > 5 else 0,
            "height": 400,
            "width": "auto"
        }
        
        return metadata
    
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
