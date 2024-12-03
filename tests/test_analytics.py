import os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestAnalytics:
    def __init__(self):
        """Initialize the test analytics with required directories."""
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "data" / "tests-data"
        self.analytics_dir = self.project_root / "analytics" / "reports" / "tests"
        
        # Ensure analytics directory exists
        self.analytics_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Analytics directory: {self.analytics_dir}")
    
    def load_test_data(self) -> pd.DataFrame:
        """Load all test reports from CSV files."""
        logger.info("Loading test data...")
        all_files = list(self.data_dir.glob("test_report_*.csv"))
        
        if not all_files:
            logger.warning("No test report files found")
            return pd.DataFrame()
        
        dfs = []
        for file in all_files:
            try:
                df = pd.read_csv(file)
                dfs.append(df)
            except Exception as e:
                logger.error(f"Error reading file {file}: {str(e)}")
        
        if not dfs:
            return pd.DataFrame()
            
        return pd.concat(dfs, ignore_index=True)
    
    def generate_daily_chart(self, df: pd.DataFrame) -> str:
        """Generate stacked bar chart for daily test results."""
        if df.empty:
            logger.warning("No data available for chart generation")
            return ""
        
        # Group by date and status, count occurrences
        daily_results = df.groupby(['date', 'status']).size().unstack(fill_value=0)
        
        # Create stacked bar chart
        fig = go.Figure()
        
        if 'PASS' in daily_results.columns:
            fig.add_trace(go.Bar(
                x=daily_results.index,
                y=daily_results['PASS'],
                name='Passed',
                marker_color='green'
            ))
        
        if 'FAIL' in daily_results.columns:
            fig.add_trace(go.Bar(
                x=daily_results.index,
                y=daily_results['FAIL'],
                name='Failed',
                marker_color='red'
            ))
        
        fig.update_layout(
            title='Daily Test Results',
            xaxis_title='Date',
            yaxis_title='Number of Tests',
            barmode='stack'
        )
        
        # Save the chart
        output_file = self.analytics_dir / f"daily_test_results_{datetime.now().strftime('%Y%m%d')}.html"
        fig.write_html(str(output_file))
        logger.info(f"Chart saved to: {output_file}")
        
        return str(output_file)

def generate_analytics():
    """Generate all analytics reports."""
    try:
        analytics = TestAnalytics()
        df = analytics.load_test_data()
        if not df.empty:
            chart_file = analytics.generate_daily_chart(df)
            logger.info("Analytics generation completed successfully")
            return chart_file
        else:
            logger.warning("No data available for analytics")
            return ""
    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        raise

if __name__ == "__main__":
    generate_analytics() 