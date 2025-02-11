from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass
from typing import Dict, List, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
from pydantic import Field
import random
from datetime import timedelta
from abi import logger

LOGO_URL = "https://logo.clearbit.com/plotly.com"

@dataclass
class PlotlyAnalyticsConfiguration(IntegrationConfiguration):
    """Configuration for Plotly Analytics.
    
    Attributes:
        width (int): Chart width in pixels
        height (int): Chart height in pixels
        title_font_family (str): Font family for titles
        title_font_size (int): Font size for titles
        axis_font_family (str): Font family for axis labels
        axis_font_size (int): Font size for axis labels
        plot_bgcolor (str): Background color for plot area
        paper_bgcolor (str): Background color for entire figure
    """
    width: int = 1200
    height: int = 800
    title_font_family: str = "arial"
    title_font_size: int = 18
    axis_font_family: str = "arial"
    axis_font_size: int = 10
    plot_bgcolor: str = "#ffffff"
    paper_bgcolor: str = "white"

class PlotlyAnalytics(Integration):
    """Generate data visualizations using Plotly."""

    __configuration: PlotlyAnalyticsConfiguration

    def __init__(self, configuration: PlotlyAnalyticsConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _generate_layout(self, title: str, xaxis_title: str = None, yaxis_title: str = None) -> dict:
        """Generate standard layout configuration for charts.
        
        Args:
            title (str): Chart title
            xaxis_title (str, optional): X-axis title
            yaxis_title (str, optional): Y-axis title
            
        Returns:
            dict: Layout configuration dictionary
        """
        layout = {
            "title": {
                "text": title,
                "font": {
                    "family": str(self.__configuration.title_font_family),
                    "size": int(self.__configuration.title_font_size),
                    "color": "black"
                }
            },
            "plot_bgcolor": str(self.__configuration.plot_bgcolor),
            "paper_bgcolor": str(self.__configuration.paper_bgcolor), 
            "width": int(self.__configuration.width),
            "height": int(self.__configuration.height),
        }
        if xaxis_title:
            layout["xaxis"] = {
                "title": {
                    "text": xaxis_title,
                    "font": {
                        "family": self.__configuration.axis_font_family,
                        "size": self.__configuration.axis_font_size,
                        "color": "black"
                    }
                }
            }
            
        if yaxis_title:
            layout["yaxis"] = {
                "title": {
                    "text": yaxis_title,
                    "font": {
                        "family": str(self.__configuration.axis_font_family),
                        "size": int(self.__configuration.axis_font_size),
                        "color": "black"
                    }
                }
            }
        return layout
    
    def _generate_fake_data(self, chart_type: str, **kwargs) -> dict:
        """Generate fake data for different chart types.
        
        Args:
            chart_type (str): Type of chart to generate data for. 
                Options: 'barline', 'bubble', 'candlestick', 'heatmap', 'treemap', 
                        'mapchart', 'pie', 'waterfall', 'gantt', 'line', 'horizontal_bar',
                        'vertical_bar', 'leaderboard'
            **kwargs: Additional parameters like n_points, date_range, etc.
        
        Returns:
            dict: Dictionary containing the required data for the specified chart type
        """
        n_points = kwargs.get('n_points', 10)
        
        if chart_type == 'barline':
            return {
                'x_data': [f"Month {i}" for i in range(1, 13)],
                'y_data_bar': [random.randint(50, 150) for _ in range(12)],
                'y_data_line': [random.randint(5, 15) for _ in range(12)]
            }
            
        elif chart_type == 'bubble':
            return {
                'x_data': [random.uniform(0, 100) for _ in range(n_points)],
                'y_data': [random.uniform(0, 100) for _ in range(n_points)],
                'size_data': [random.randint(10, 50) for _ in range(n_points)]
            }
            
        elif chart_type == 'candlestick':
            base_date = datetime.now()
            base_price = 100
            dates = [(base_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(n_points)]
            prices = []
            
            for _ in range(n_points):
                open_price = base_price + random.uniform(-5, 5)
                close_price = base_price + random.uniform(-5, 5)
                high_price = max(open_price, close_price) + random.uniform(0, 3)
                low_price = min(open_price, close_price) - random.uniform(0, 3)
                prices.append((open_price, high_price, low_price, close_price))
                base_price = close_price
                
            return {
                'x_data': dates,
                'open_data': [p[0] for p in prices],
                'high_data': [p[1] for p in prices],
                'low_data': [p[2] for p in prices],
                'close_data': [p[3] for p in prices]
            }
            
        elif chart_type == 'heatmap':
            size = kwargs.get('size', 8)
            return {
                'z_data': [[random.randint(0, 100) for _ in range(size)] for _ in range(size)],
                'x_labels': [f"X{i}" for i in range(size)],
                'y_labels': [f"Y{i}" for i in range(size)]
            }
            
        elif chart_type == 'treemap':
            return {
                'labels': ['Total', 'A', 'B', 'A1', 'A2', 'B1', 'B2'],
                'parents': ['', 'Total', 'Total', 'A', 'A', 'B', 'B'],
                'values': [100, 60, 40, 30, 30, 20, 20]
            }
            
        elif chart_type == 'mapchart':
            cities = {
                'New York': (40.7128, -74.0060),
                'London': (51.5074, -0.1278),
                'Tokyo': (35.6762, 139.6503),
                'Sydney': (-33.8688, 151.2093),
                'Paris': (48.8566, 2.3522)
            }
            return {
                'lat_data': [coord[0] for coord in cities.values()],
                'lon_data': [coord[1] for coord in cities.values()],
                'text': list(cities.keys())
            }
            
        elif chart_type == 'pie':
            return {
                'labels': [f'Category {i}' for i in range(n_points)],
                'values': [random.randint(10, 100) for _ in range(n_points)]
            }
            
        elif chart_type == 'waterfall':
            return {
                'x_data': ['Start'] + [f'Step {i}' for i in range(1, n_points-1)] + ['End'],
                'y_data': [100] + [random.randint(-30, 30) for _ in range(n_points-2)] + [random.randint(-20, 50)]
            }
            
        elif chart_type == 'gantt':
            base_date = datetime.now()
            tasks = [f'Task {i}' for i in range(n_points)]
            start_dates = [(base_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(n_points)]
            end_dates = [(base_date + timedelta(days=i+random.randint(3, 10))).strftime('%Y-%m-%d') for i in range(n_points)]
            return {
                'tasks': tasks,
                'start_dates': start_dates,
                'end_dates': end_dates
            }
            
        elif chart_type in ['line', 'horizontal_bar', 'vertical_bar']:
            return {
                'x_data': [f'Point {i}' for i in range(n_points)],
                'y_data': [random.randint(10, 100) for _ in range(n_points)]
            }
            
        elif chart_type == 'leaderboard':
            return {
                'x_data': [f'Player {i}' for i in range(n_points)],
                'y_data': sorted([random.randint(100, 1000) for _ in range(n_points)], reverse=True)
            }
            
        else:
            raise ValueError(f"Unknown chart type: {chart_type}")
        
    def _save_graph(self, fig, filename: str, format: str = "png") -> str:
        """Save a Plotly graph to a file.
        
        Args:
            fig: Plotly figure object to save
            filename (str): Name of the file to save (without extension)
            format (str, optional): Format to save in ('png', 'html' or 'json'). Defaults to "png"
            
        Returns:
            str: Full path to the saved file
            
        Raises:
            ValueError: If format is not 'png', 'html' or 'json'
            
        Example:
            >>> fig = analytics.create_linechart(x_data=[1,2,3], y_data=[4,5,6])
            >>> path = analytics.save_graph(fig, "my_chart")
        """
        import os
        from pathlib import Path

        # Format the filename to be a valid filename
        filename = filename.replace(" ", "_").lower()
        
        # Create analytics directory if it doesn't exist
        save_dir = Path("src/data/analytics")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == "html":
            filepath = save_dir / f"{filename}.html"
            fig.write_html(filepath)
        elif format.lower() == "json":
            filepath = save_dir / f"{filename}.json"
            fig.write_json(filepath)
        elif format.lower() == "png":
            filepath = save_dir / f"{filename}.png"
            fig.write_image(filepath)
        else:
            raise ValueError("Format must be either 'png', 'html' or 'json'")
            
        logger.info(f"Saved graph to {filepath}")
        return str(filepath)

    def create_barline_chart(
            self, 
            x_data=None,
            y_data_bars=None,
            y_data_lines=None,
            bar_names=None,
            line_names=None,
            title="Barline Chart", 
            xaxis_title="X Axis", 
            yaxis_title_l="Left Y Axis", 
            yaxis_title_r="Right Y Axis",
            colors_bars=None,
            colors_lines=None
        ):
        """Create a combined bar and line chart visualization with multiple series.
        
        Args:
            x_data (list): Data for x-axis
            y_data_bars (list of lists): List of y-values for each bar series
            y_data_lines (list of lists): List of y-values for each line series
            bar_names (list): Names for each bar series
            line_names (list): Names for each line series
            title (str): Chart title
            xaxis_title (str): X-axis label
            yaxis_title_l (str): Left y-axis label
            yaxis_title_r (str): Right y-axis label
            colors_bars (list): Colors for bar series
            colors_lines (list): Colors for line series
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if x_data is None or y_data_bars is None or y_data_lines is None:
            fake_data = self._generate_fake_data('barline')
            x_data = x_data or fake_data['x_data']
            y_data_bars = y_data_bars or [fake_data['y_data_bar']]
            y_data_lines = y_data_lines or [fake_data['y_data_line']]
        
        # Ensure y_data_bars and y_data_lines are lists of lists
        if not isinstance(y_data_bars[0], list):
            y_data_bars = [y_data_bars]
        if not isinstance(y_data_lines[0], list):
            y_data_lines = [y_data_lines]
        
        # Set default names if not provided
        bar_names = bar_names or [f'Bar {i+1}' for i in range(len(y_data_bars))]
        line_names = line_names or [f'Line {i+1}' for i in range(len(y_data_lines))]
        
        # Set default colors if not provided
        default_bar_colors = ['rgba(55, 128, 191, 0.7)', 'rgba(219, 64, 82, 0.7)', 'rgba(128, 0, 128, 0.7)']
        default_line_colors = ['rgba(50, 171, 96, 0.7)', 'rgba(255, 144, 14, 0.7)', 'rgba(0, 128, 128, 0.7)']
        colors_bars = colors_bars or default_bar_colors
        colors_lines = colors_lines or default_line_colors
        
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Add bar traces
        for i, (y_data, name, color) in enumerate(zip(y_data_bars, bar_names, colors_bars)):
            fig.add_trace(
                go.Bar(
                    name=name,
                    x=x_data,
                    y=y_data,
                    yaxis='y',
                    marker=dict(color=color),
                    offsetgroup=i  # Prevents bars from overlapping
                )
            )
        
        # Add line traces
        for y_data, name, color in zip(y_data_lines, line_names, colors_lines):
            fig.add_trace(
                go.Scatter(
                    name=name,
                    x=x_data,
                    y=y_data,
                    yaxis='y2',
                    line=dict(color=color, width=2.5),
                    mode='lines'
                )
            )
        
        # Update layout
        layout = self._generate_layout(title, xaxis_title)
        fig.update_layout(layout)
        
        # Set y-axes titles
        fig.update_yaxes(
            title_text=yaxis_title_l,
            title_font=dict(
                family=self.__configuration.axis_font_family,
                size=self.__configuration.axis_font_size,
                color="black"
            ),
            secondary_y=False
        )
        fig.update_yaxes(
            title_text=yaxis_title_r,
            title_font=dict(
                family=self.__configuration.axis_font_family,
                size=self.__configuration.axis_font_size,
                color="black"
            ),
            secondary_y=True
        )
        
        # Show legend if there are multiple series
        if len(y_data_bars) > 1 or len(y_data_lines) > 1:
            fig.update_layout(showlegend=True)
        else:
            fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_bubble_chart(
            self, 
            x_data=None,
            y_data=None,
            size_data=None,
            title="Bubble Chart",
            xaxis_title="X Axis",
            yaxis_title="Y Axis"
        ):
        """Create a bubble chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random data will be generated
            y_data (list, optional): Data for y-axis. If None, random data will be generated
            size_data (list, optional): Data for bubble sizes. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Bubble Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "X Axis"
            yaxis_title (str, optional): Y-axis label. Defaults to "Y Axis"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if x_data is None or y_data is None or size_data is None:
            fake_data = self._generate_fake_data('bubble')
            x_data = x_data or fake_data['x_data']
            y_data = y_data or fake_data['y_data']
            size_data = size_data or fake_data['size_data']

        fig = go.Figure(data=[go.Scatter(
            x=x_data,
            y=y_data,
            mode='markers',
            marker=dict(size=size_data)
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_candlestick_chart(
            self,
            x_data=None,
            open_data=None,
            high_data=None,
            low_data=None,
            close_data=None,
            title="Candlestick Chart",
            xaxis_title="Date",
            yaxis_title="Price"
        ):
        """Create a candlestick chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random dates will be generated
            open_data (list, optional): Data for open prices. If None, random data will be generated
            high_data (list, optional): Data for high prices. If None, random data will be generated
            low_data (list, optional): Data for low prices. If None, random data will be generated
            close_data (list, optional): Data for close prices. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Candlestick Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "Date"
            yaxis_title (str, optional): Y-axis label. Defaults to "Price"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if any(data is None for data in [x_data, open_data, high_data, low_data, close_data]):
            fake_data = self._generate_fake_data('candlestick')
            x_data = x_data or fake_data['x_data']
            open_data = open_data or fake_data['open_data']
            high_data = high_data or fake_data['high_data']
            low_data = low_data or fake_data['low_data']
            close_data = close_data or fake_data['close_data']

        fig = go.Figure(data=[go.Candlestick(
            x=x_data,
            open=open_data,
            high=high_data,
            low=low_data,
            close=close_data
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        
        return self._save_graph(fig, title)

    def create_heatmap(
            self,
            z_data=None,
            x_labels=None,
            y_labels=None,
            title="Heatmap"
        ):
        """Create a heatmap visualization.
        
        Args:
            z_data (list of lists, optional): 2D array of values to plot. If None, random data will be generated
            x_labels (list, optional): Labels for x-axis. If None, default labels will be generated
            y_labels (list, optional): Labels for y-axis. If None, default labels will be generated
            title (str, optional): Chart title. Defaults to "Heatmap"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if z_data is None:
            fake_data = self._generate_fake_data('heatmap')
            z_data = fake_data['z_data']
            x_labels = x_labels or fake_data['x_labels']
            y_labels = y_labels or fake_data['y_labels']

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=x_labels,
            y=y_labels
        ))
        
        fig.update_layout(self._generate_layout(title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_gantt_chart(
            self,
            tasks=None,
            start_dates=None,
            end_dates=None,
            title="Gantt Chart",
            xaxis_title="Date",
            yaxis_title="Tasks"
        ):
        """Create a gantt chart visualization.
        
        Args:
            tasks (list, optional): List of task names. If None, random data will be generated
            start_dates (list, optional): List of start dates. If None, random data will be generated
            end_dates (list, optional): List of end dates. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Gantt Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "Date"
            yaxis_title (str, optional): Y-axis label. Defaults to "Tasks"
        
        Returns:
            str: Path to the saved chart file
        """
        if any(data is None for data in [tasks, start_dates, end_dates]):
            fake_data = self._generate_fake_data('gantt')
            tasks = tasks or fake_data['tasks']
            start_dates = start_dates or fake_data['start_dates']
            end_dates = end_dates or fake_data['end_dates']

        fig = go.Figure([
            dict(
                type='scatter',
                x=start_dates + end_dates,
                y=tasks + tasks,
                mode='lines',
                line=dict(color='rgb(255,0,0)', width=0.5),
                hoverinfo='none'
            )
        ])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        
        return self._save_graph(fig, title)

    def create_horizontal_barchart(
            self,
            x_data=None,
            y_data=None,
            title="Horizontal Bar Chart",
            xaxis_title="Value",
            yaxis_title="Category"
        ):
        """Create a horizontal bar chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random data will be generated
            y_data (list, optional): Data for y-axis. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Horizontal Bar Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "Value"
            yaxis_title (str, optional): Y-axis label. Defaults to "Category"
        
        Returns:
            str: Path to the saved chart file
        """
        if x_data is None or y_data is None:
            fake_data = self._generate_fake_data('horizontal_bar')
            x_data = x_data or fake_data['y_data']  # Swap x and y for horizontal
            y_data = y_data or fake_data['x_data']

        fig = go.Figure(data=[go.Bar(
            x=x_data,
            y=y_data,
            orientation='h'
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_leaderboard(
            self,
            x_data=None,
            y_data=None,
            title="Leaderboard",
            xaxis_title="Player",
            yaxis_title="Score"
        ):
        """Create a leaderboard visualization.
        
        Args:
            x_data (list, optional): Data for x-axis (e.g. player names). If None, random data will be generated
            y_data (list, optional): Data for y-axis (e.g. scores). If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Leaderboard"
            xaxis_title (str, optional): X-axis label. Defaults to "Player"
            yaxis_title (str, optional): Y-axis label. Defaults to "Score"
        
        Returns:
            str: Path to the saved chart file
        """
        if x_data is None or y_data is None:
            fake_data = self._generate_fake_data('leaderboard')
            x_data = x_data or fake_data['x_data']
            y_data = y_data or fake_data['y_data']

        fig = go.Figure(data=[go.Bar(
            x=x_data,
            y=y_data,
            marker_color='rgb(158,202,225)',
            text=y_data,
            textposition='auto',
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_linechart(
            self,
            x_data=None,
            y_data=None,
            title="Line Chart",
            xaxis_title="X Axis",
            yaxis_title="Y Axis"
        ):
        """Create a line chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random data will be generated
            y_data (list, optional): Data for y-axis. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Line Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "X Axis"
            yaxis_title (str, optional): Y-axis label. Defaults to "Y Axis"
        
        Returns:
            str: Path to the saved chart file
        """
        if x_data is None or y_data is None:
            fake_data = self._generate_fake_data('line')
            x_data = x_data or fake_data['x_data']
            y_data = y_data or fake_data['y_data']

        fig = go.Figure(data=go.Scatter(
            x=x_data,
            y=y_data,
            mode='lines'
        ))
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)

    def create_mapchart(
            self,
            lat_data=None,
            lon_data=None,
            text=None,
            title="Map Chart"
        ):
        """Create a map visualization with markers.
        
        Args:
            lat_data (list, optional): Latitude values. If None, random data will be generated
            lon_data (list, optional): Longitude values. If None, random data will be generated
            text (list, optional): Hover text for each point. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Map Chart"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if any(data is None for data in [lat_data, lon_data]):
            fake_data = self._generate_fake_data('mapchart')
            lat_data = lat_data or fake_data['lat_data']
            lon_data = lon_data or fake_data['lon_data']
            text = text or fake_data['text']

        fig = go.Figure(data=go.Scattergeo(
            lon=lon_data,
            lat=lat_data,
            text=text,
            mode='markers'
        ))
        
        fig.update_layout(self._generate_layout(title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)
    
    def create_piechart(
            self,
            labels=None,
            values=None,
            title="Pie Chart"
        ):
        """Create a pie chart visualization.
        
        Args:
            labels (list, optional): Labels for each pie slice. If None, random data will be generated
            values (list, optional): Values for each pie slice. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Pie Chart"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if labels is None or values is None:
            # Add pie chart to _generate_fake_data if not already present
            labels = labels or [f'Category {i}' for i in range(5)]
            values = values or [random.randint(10, 100) for _ in range(5)]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values
        )])
        
        fig.update_layout(self._generate_layout(title))
        
        return self._save_graph(fig, title)

    def create_treemap(
            self,
            labels=None,
            parents=None,
            values=None,
            title="Treemap"
        ):
        """Create a treemap visualization.
        
        Args:
            labels (list, optional): Names of all nodes. If None, random data will be generated
            parents (list, optional): Parent names for each node. If None, random data will be generated
            values (list, optional): Values for each node. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Treemap"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if any(data is None for data in [labels, parents, values]):
            fake_data = self._generate_fake_data('treemap')
            labels = labels or fake_data['labels']
            parents = parents or fake_data['parents']
            values = values or fake_data['values']

        fig = go.Figure(data=[go.Treemap(
            labels=labels,
            parents=parents,
            values=values
        )])
        
        fig.update_layout(self._generate_layout(title))
        
        return self._save_graph(fig, title)

    def create_vertical_barchart(
            self,
            x_data=None,
            y_data=None,
            title="Vertical Bar Chart",
            xaxis_title="Category",
            yaxis_title="Value"
        ):
        """Create a vertical bar chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random data will be generated
            y_data (list, optional): Data for y-axis. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Vertical Bar Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "Category"
            yaxis_title (str, optional): Y-axis label. Defaults to "Value"
        
        Returns:
            str: Path to the saved chart file
        """
        if x_data is None or y_data is None:
            fake_data = self._generate_fake_data('vertical_bar')
            x_data = x_data or fake_data['x_data']
            y_data = y_data or fake_data['y_data']

        fig = go.Figure(data=[go.Bar(
            x=x_data,
            y=y_data
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        fig.update_traces(showlegend=False)
        
        return self._save_graph(fig, title)
    
    def create_waterfall_chart(
            self,
            x_data=None,
            y_data=None,
            title="Waterfall Chart",
            xaxis_title="X Axis",
            yaxis_title="Y Axis"
        ):
        """Create a waterfall chart visualization.
        
        Args:
            x_data (list, optional): Data for x-axis. If None, random data will be generated
            y_data (list, optional): Data for y-axis. If None, random data will be generated
            title (str, optional): Chart title. Defaults to "Waterfall Chart"
            xaxis_title (str, optional): X-axis label. Defaults to "X Axis"
            yaxis_title (str, optional): Y-axis label. Defaults to "Y Axis"
            
        Returns:
            str: Path to the saved chart file
        """
        # Generate fake data if not provided
        if x_data is None or y_data is None:
            # Add waterfall to _generate_fake_data if not already present
            x_data = x_data or ['Start', 'Step 1', 'Step 2', 'Step 3', 'End']
            y_data = y_data or [100, -20, 30, -10, 40]

        fig = go.Figure(data=[go.Waterfall(
            x=x_data,
            y=y_data,
            connector={"line": {"color": "rgb(63, 63, 63)"}}
        )])
        
        fig.update_layout(self._generate_layout(title, xaxis_title, yaxis_title))
        
        return self._save_graph(fig, title)

def as_tools(configuration: PlotlyAnalyticsConfiguration):
    """Convert Plotly Analytics into LangChain tools.
    
    Args:
        configuration (PlotlyAnalyticsConfiguration): Configuration for the analytics
    
    Returns:
        list[StructuredTool]: List of LangChain tools for chart creation
    """
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import Optional, List
    
    analytics = PlotlyAnalytics(configuration)

    class BarLineChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis. If not provided, random dates will be generated")
        y_data_bars: Optional[List[List]] = Field(default=None, description="Data for bar chart y-axis. If not provided, random values will be generated") 
        y_data_lines: Optional[List[List]] = Field(default=None, description="Data for line chart y-axis. If not provided, random values will be generated")
        bar_names: Optional[List[str]] = Field(default=None, description="Names for each bar series")
        line_names: Optional[List[str]] = Field(default=None, description="Names for each line series")
        title: str = Field(default="Barline Chart", description="Chart title")
        xaxis_title: str = Field(default="X Axis", description="X-axis label")
        yaxis_title_l: str = Field(default="Left Y Axis", description="Left y-axis label")
        yaxis_title_r: str = Field(default="Right Y Axis", description="Right y-axis label")
        colors_bars: Optional[List[str]] = Field(default=None, description="Colors for bar series")
        colors_lines: Optional[List[str]] = Field(default=None, description="Colors for line series")

    class BubbleChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis")
        size_data: Optional[List] = Field(default=None, description="Data for bubble sizes")
        title: str = Field(default="Bubble Chart", description="Chart title")
        xaxis_title: str = Field(default="X Axis", description="X-axis label")
        yaxis_title: str = Field(default="Y Axis", description="Y-axis label")

    class CandlestickChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis (dates)")
        open_data: Optional[List] = Field(default=None, description="Data for open prices")
        high_data: Optional[List] = Field(default=None, description="Data for high prices")
        low_data: Optional[List] = Field(default=None, description="Data for low prices")
        close_data: Optional[List] = Field(default=None, description="Data for close prices")
        title: str = Field(default="Candlestick Chart", description="Chart title")
        xaxis_title: str = Field(default="Date", description="X-axis label")
        yaxis_title: str = Field(default="Price", description="Y-axis label")

    class HeatmapSchema(BaseModel):
        z_data: Optional[List[List]] = Field(default=None, description="2D array of values to plot")
        x_labels: Optional[List] = Field(default=None, description="Labels for x-axis")
        y_labels: Optional[List] = Field(default=None, description="Labels for y-axis")
        title: str = Field(default="Heatmap", description="Chart title")

    class TreemapSchema(BaseModel):
        labels: Optional[List] = Field(default=None, description="Names of all nodes")
        parents: Optional[List] = Field(default=None, description="Parent names for each node")
        values: Optional[List] = Field(default=None, description="Values for each node")
        title: str = Field(default="Treemap", description="Chart title")

    class MapChartSchema(BaseModel):
        lat_data: Optional[List] = Field(default=None, description="Latitude values")
        lon_data: Optional[List] = Field(default=None, description="Longitude values")
        text: Optional[List] = Field(default=None, description="Hover text for each point")
        title: str = Field(default="Map Chart", description="Chart title")

    class PieChartSchema(BaseModel):
        labels: Optional[List] = Field(default=None, description="Labels for each pie slice")
        values: Optional[List] = Field(default=None, description="Values for each pie slice")
        title: str = Field(default="Pie Chart", description="Chart title")

    class WaterfallChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis")
        title: str = Field(default="Waterfall Chart", description="Chart title")
        xaxis_title: str = Field(default="X Axis", description="X-axis label")
        yaxis_title: str = Field(default="Y Axis", description="Y-axis label")

    class GanttChartSchema(BaseModel):
        tasks: Optional[List] = Field(default=None, description="List of task names")
        start_dates: Optional[List] = Field(default=None, description="List of start dates")
        end_dates: Optional[List] = Field(default=None, description="List of end dates")
        title: str = Field(default="Gantt Chart", description="Chart title")
        xaxis_title: str = Field(default="Date", description="X-axis label")
        yaxis_title: str = Field(default="Tasks", description="Y-axis label")

    class BarChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis")
        title: str = Field(default="Bar Chart", description="Chart title")
        xaxis_title: str = Field(default="Category", description="X-axis label")
        yaxis_title: str = Field(default="Value", description="Y-axis label")

    class LeaderboardSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis (e.g. player names)")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis (e.g. scores)")
        title: str = Field(default="Leaderboard", description="Chart title")
        xaxis_title: str = Field(default="Player", description="X-axis label")
        yaxis_title: str = Field(default="Score", description="Y-axis label")

    class LineChartSchema(BaseModel):
        x_data: Optional[List] = Field(default=None, description="Data for x-axis")
        y_data: Optional[List] = Field(default=None, description="Data for y-axis")
        title: str = Field(default="Line Chart", description="Chart title")
        xaxis_title: str = Field(default="X Axis", description="X-axis label")
        yaxis_title: str = Field(default="Y Axis", description="Y-axis label")

    analytics = PlotlyAnalytics(configuration)
    
    return [
        StructuredTool(
            name="plotly_barline_chart",
            description="Create a combined bar and line chart visualization. Perfect for comparing revenue (bars) against profit margins (line) over time. This dual-axis visualization helps identify correlations between different business metrics.",
            func=lambda **kwargs: analytics.create_barline_chart(**kwargs),
            args_schema=BarLineChartSchema
        ),
        StructuredTool(
            name="plotly_bubble_chart",
            description="Create a bubble chart visualization. Ideal for portfolio analysis where three dimensions (e.g., market size, growth rate, and current revenue) need to be visualized simultaneously. Commonly used in strategic planning and market analysis.",
            func=lambda **kwargs: analytics.create_bubble_chart(**kwargs),
            args_schema=BubbleChartSchema
        ),
        StructuredTool(
            name="plotly_candlestick_chart",
            description="Create a candlestick chart visualization. Essential for financial analysis and stock trading, showing opening, closing, high, and low values over time. Helps identify market trends and potential trading opportunities.",
            func=lambda **kwargs: analytics.create_candlestick_chart(**kwargs),
            args_schema=CandlestickChartSchema
        ),
        StructuredTool(
            name="plotly_heatmap",
            description="Create a heatmap visualization. Excellent for identifying patterns in large datasets such as customer behavior across different times and locations. Widely used in retail analytics and customer engagement analysis.",
            func=lambda **kwargs: analytics.create_heatmap(**kwargs),
            args_schema=HeatmapSchema
        ),
        StructuredTool(
            name="plotly_treemap",
            description="Create a treemap visualization. Perfect for hierarchical data representation such as market segmentation or budget allocation. Helps stakeholders quickly understand proportional relationships and nested categories.",
            func=lambda **kwargs: analytics.create_treemap(**kwargs),
            args_schema=TreemapSchema
        ),
        StructuredTool(
            name="plotly_mapchart",
            description="Create a map visualization with markers. Essential for geographical business analysis such as store performance by location or market penetration analysis. Helps identify regional trends and opportunities.",
            func=lambda **kwargs: analytics.create_mapchart(**kwargs),
            args_schema=MapChartSchema
        ),
        StructuredTool(
            name="plotly_piechart",
            description="Create a pie chart visualization. Ideal for showing market share distribution or budget allocation across departments. Provides an immediate visual understanding of proportional relationships.",
            func=lambda **kwargs: analytics.create_piechart(**kwargs),
            args_schema=PieChartSchema
        ),
        StructuredTool(
            name="plotly_waterfall_chart",
            description="Create a waterfall chart visualization. Perfect for explaining cumulative effect of sequential business events like revenue build-up or cost breakdown analysis. Commonly used in financial planning and variance analysis.",
            func=lambda **kwargs: analytics.create_waterfall_chart(**kwargs),
            args_schema=WaterfallChartSchema
        ),
        StructuredTool(
            name="plotly_gantt_chart",
            description="Create a Gantt chart visualization. Essential for project management and timeline visualization across teams and departments. Helps track progress and dependencies in complex business projects.",
            func=lambda **kwargs: analytics.create_gantt_chart(**kwargs),
            args_schema=GanttChartSchema
        ),
        StructuredTool(
            name="plotly_horizontal_barchart",
            description="Create a horizontal bar chart visualization. Excellent for comparing values across different categories, especially with long category names. Commonly used for survey results and performance comparisons.",
            func=lambda **kwargs: analytics.create_horizontal_barchart(**kwargs),
            args_schema=BarChartSchema
        ),
        StructuredTool(
            name="plotly_vertical_barchart",
            description="Create a vertical bar chart visualization. Perfect for showing trends over time or comparing values across categories. Widely used in sales analysis and performance tracking.",
            func=lambda **kwargs: analytics.create_vertical_barchart(**kwargs),
            args_schema=BarChartSchema
        ),
        StructuredTool(
            name="plotly_leaderboard",
            description="Create a leaderboard visualization. Ideal for sales team performance rankings or product performance comparisons. Drives competitive behavior and highlights top performers in an organization.",
            func=lambda **kwargs: analytics.create_leaderboard(**kwargs),
            args_schema=LeaderboardSchema
        ),
        StructuredTool(
            name="plotly_linechart",
            description="Create a line chart visualization. Essential for tracking trends over time such as sales growth or market performance. Perfect for showing continuous data and identifying patterns in business metrics.",
            func=lambda **kwargs: analytics.create_linechart(**kwargs),
            args_schema=LineChartSchema
        )
    ]
