import dash
from dash import html, dcc
from typing import List, Dict, Any
from dataclasses import dataclass
from src.core.modules.common.analytics.visualization.PlotlyAnalytics import (
    PlotlyAnalytics,
    PlotlyAnalyticsConfiguration,
)


@dataclass
class DashPlotlyAnalyticsConfiguration:
    """Configuration for DashPlotlyAnalytics.

    Attributes:
        title (str): Dashboard title
        theme (str): Color theme ('light' or 'dark')
        layout_type (str): Layout type ('grid' or 'flex')
        plotly_config (PlotlyAnalyticsConfiguration): Configuration for Plotly charts
    """

    title: str
    theme: str = "light"
    layout_type: str = "grid"
    plotly_config: PlotlyAnalyticsConfiguration = PlotlyAnalyticsConfiguration()


class DashPlotlyAnalytics:
    """Helper class for building Dash Plotly dashboards.

    This class provides methods to easily create and customize dashboards
    with common components like navigation bars, KPI sections, and charts.

    Attributes:
        __app (dash.Dash): The Dash application instance
        __config (DashPlotlyAnalyticsConfiguration): Dashboard configuration
        __analytics (PlotlyAnalytics): Plotly analytics instance for creating charts
    """

    def __init__(self, config: DashPlotlyAnalyticsConfiguration):
        """Initialize the dashboard builder.

        Args:
            config (DashPlotlyAnalyticsConfiguration): Dashboard configuration
        """
        self.__app = dash.Dash(__name__, suppress_callback_exceptions=True)
        self.__config = config
        self.__analytics = PlotlyAnalytics(config.plotly_config)

        # Set theme-based styles
        self.__styles = self.__get_theme_styles()

    def __get_theme_styles(self) -> Dict[str, Dict]:
        """Get theme-based styles for dashboard components."""
        if self.__config.theme == "dark":
            return {
                "main": {
                    "backgroundColor": "#181b1d",
                    "color": "white",
                    "fontFamily": "Arial, sans-serif",
                },
                "navbar": {
                    "backgroundColor": "#2c3034",
                    "color": "white",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.2)",
                },
                "card": {
                    "backgroundColor": "#2c3034",
                    "color": "white",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                },
            }
        else:
            return {
                "main": {
                    "backgroundColor": "#ffffff",
                    "color": "black",
                    "fontFamily": "Arial, sans-serif",
                },
                "navbar": {
                    "backgroundColor": "white",
                    "color": "black",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                },
                "card": {
                    "backgroundColor": "white",
                    "color": "black",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                },
            }

    def create_navbar(
        self, logo_url: str = None, filters: List[Dict] = None
    ) -> html.Div:
        """Create a navigation bar component.

        Args:
            logo_url (str, optional): URL for the logo image
            filters (List[Dict], optional): List of filter configurations
                Each filter should have 'options' and 'value' keys

        Returns:
            html.Div: Navigation bar component
        """
        navbar_style = {
            **self.__styles["navbar"],
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "1rem",
            "marginBottom": "2rem",
        }

        # Create logo component if URL provided
        logo = html.Img(src=logo_url, style={"height": "50px"}) if logo_url else None

        # Create filters if provided
        filter_components = []
        if filters:
            for f in filters:
                filter_components.append(
                    dcc.Dropdown(
                        options=f["options"],
                        value=f["value"],
                        style={
                            "width": "150px",
                            "minWidth": "120px",
                            "marginRight": "0.5rem",
                        },
                    )
                )

        return html.Div(
            [
                logo if logo else None,
                html.Div(
                    filter_components,
                    style={"display": "flex", "flexWrap": "wrap", "gap": "0.5rem"},
                )
                if filter_components
                else None,
            ],
            style=navbar_style,
        )

    def create_kpi_section(self, kpis: List[Dict[str, Any]]) -> html.Div:
        """Create a section of KPI cards.

        Args:
            kpis (List[Dict]): List of KPI configurations
                Each KPI should have 'title', 'value', and optionally 'change' keys

        Returns:
            html.Div: KPI section component
        """
        kpi_style = {
            **self.__styles["card"],
            "padding": "1rem",
            "borderRadius": "8px",
            "textAlign": "center",
            "flex": "1",
            "minWidth": "250px",
        }

        kpi_cards = []
        for kpi in kpis:
            change_color = "green" if kpi.get("change", 0) >= 0 else "red"
            kpi_cards.append(
                html.Div(
                    [
                        html.H4(kpi["title"]),
                        html.H3(kpi["value"]),
                        html.P(
                            f"{kpi.get('change', 0):+.1f}% vs prev",
                            style={"color": change_color},
                        )
                        if "change" in kpi
                        else None,
                    ],
                    style=kpi_style,
                )
            )

        return html.Div(
            kpi_cards,
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(250px, 1fr))",
                "gap": "1rem",
                "marginBottom": "2rem",
                "width": "100%",
            },
        )

    def create_chart_grid(
        self, charts: List[Dict[str, Any]], columns: int = 2
    ) -> html.Div:
        """Create a grid of charts.

        Args:
            charts (List[Dict]): List of chart configurations
                Each chart should have 'figure' and optionally 'title' keys
            columns (int, optional): Number of columns in the grid. Defaults to 2

        Returns:
            html.Div: Chart grid component
        """
        chart_style = {
            **self.__styles["card"],
            "padding": "1rem",
            "borderRadius": "8px",
            "margin": "0.5rem",
            "flex": f"1 1 calc(100% / {columns} - 1rem)",
            "minWidth": "600px",
        }

        chart_components = []
        for chart in charts:
            chart_components.append(
                html.Div(
                    [
                        html.H3(chart.get("title", ""), style={"marginBottom": "1rem"}),
                        dcc.Graph(
                            figure=chart["figure"],
                            style={"height": "100%", "width": "100%"},
                        ),
                    ],
                    style=chart_style,
                )
            )

        return html.Div(
            chart_components,
            style={
                "display": "flex",
                "flexWrap": "wrap",
                "gap": "1rem",
                "justifyContent": "space-between",
                "padding": "0 1rem",
                "width": "100%",
            },
        )

    def create_layout(self, components: List[html.Div]) -> None:
        """Set the dashboard layout with the provided components.

        Args:
            components (List[html.Div]): List of dashboard components
        """
        self.__app.layout = html.Div(
            components,
            style={**self.__styles["main"], "minHeight": "100vh", "padding": "2rem"},
        )

    def run(self, debug: bool = True, port: int = 8050) -> None:
        """Run the dashboard server.

        Args:
            debug (bool, optional): Enable debug mode. Defaults to True
            port (int, optional): Port to run the server on. Defaults to 8050
        """
        self.__app.run_server(debug=debug, port=port)

    @property
    def app(self) -> dash.Dash:
        """Get the Dash application instance."""
        return self.__app

    @property
    def analytics(self) -> PlotlyAnalytics:
        """Get the PlotlyAnalytics instance."""
        return self.__analytics
