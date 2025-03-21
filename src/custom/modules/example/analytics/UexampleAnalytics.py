import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional
import io
import base64

class UexampleAnalytics:
    """Analytics for the Uexample module."""
    
    def __init__(self):
        """Initialize the analytics component."""
        pass
    
    def analyze_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze data and return results."""
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(data)
        
        # Example analysis metrics (customize based on your actual data)
        metrics = {
            "count": len(df),
            "fields": list(df.columns) if not df.empty else [],
            "summary": df.describe().to_dict() if not df.empty else {}
        }
        
        return metrics
    
    def generate_chart(self, data: List[Dict[str, Any]], x_field: str, y_field: str, 
                      chart_type: str = "bar", title: Optional[str] = None) -> str:
        """Generate a chart from the data and return as base64 encoded image."""
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        if df.empty or x_field not in df.columns or y_field not in df.columns:
            return ""
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Generate the specified chart type
        if chart_type == "bar":
            df.plot(kind="bar", x=x_field, y=y_field)
        elif chart_type == "line":
            df.plot(kind="line", x=x_field, y=y_field)
        elif chart_type == "scatter":
            df.plot(kind="scatter", x=x_field, y=y_field)
        else:
            df.plot(kind="bar", x=x_field, y=y_field)  # Default to bar
        
        # Add title if provided
        if title:
            plt.title(title)
        else:
            plt.title(f"{y_field} by {x_field}")
        
        # Add labels
        plt.xlabel(x_field)
        plt.ylabel(y_field)
        
        # Save to bytes buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        
        # Convert to base64
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        plt.close()
        
        return f"data:image/png;base64,{image_base64}"

# For testing purposes
if __name__ == "__main__":
    # Sample test data
    test_data = [
        {"category": "A", "value": 10},
        {"category": "B", "value": 15},
        {"category": "C", "value": 7},
        {"category": "D", "value": 12}
    ]
    
    analytics = UexampleAnalytics()
    
    # Test analysis
    results = analytics.analyze_data(test_data)
    print("Analysis results:", results)
    
    # Test chart generation
    chart = analytics.generate_chart(test_data, "category", "value", "bar", "Sample Chart")
    print("Chart generated with length:", len(chart))
    
    # To view the chart, you would typically embed it in HTML like:
    # print(f"<img src='{chart}' />")

