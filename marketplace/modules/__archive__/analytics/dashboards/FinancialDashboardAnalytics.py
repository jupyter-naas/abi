import dash
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Initialize the Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)

# Add default styles to the app
app.layout = html.Div(
    [
        # Your existing layout content
    ],
    style={"fontFamily": "Arial, sans-serif"},
)


# Generate some fake data
def generate_fake_data():
    dates = pd.date_range(start="2024-01-01", end="2024-03-31", freq="D")

    # Cash flow data
    cash_in = np.random.normal(100000, 15000, len(dates))
    cash_out = np.random.normal(90000, 12000, len(dates))
    balance = np.cumsum(cash_in - cash_out)

    # KPI data
    return {
        "dates": dates,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "balance": balance,
        "current_balance": balance[-1],
        "daily_avg_in": np.mean(cash_in),
        "daily_avg_out": np.mean(cash_out),
        "liquidity_ratio": cash_in.sum() / cash_out.sum(),
        "pending_payments": np.random.normal(50000, 5000),
        "forecast_balance": balance[-1] * 1.15,
    }


# Create the layout
def create_layout():
    data = generate_fake_data()

    # Navbar style
    #    navbar_style = {
    #        "display": "flex",
    #        "justifyContent": "space-between",
    #        "alignItems": "center",
    #        "padding": "1rem",
    #        "backgroundColor": "white",
    #        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
    #        "marginBottom": "2rem",
    #    }

    # KPI box style
    kpi_box_style = {
        "backgroundColor": "white",
        "padding": "1rem",
        "borderRadius": "8px",
        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
        "textAlign": "center",
        "flex": "1",
        "minWidth": "250px",
    }

    return html.Div(
        [
            # Navbar
            html.Div(
                [
                    # Logo (on left side)
                    html.Img(
                        src="https://avatars.githubusercontent.com/u/71603764?s=400&u=a06d20058028b89181e084f2e5f750d3ea271925&v=4",
                        style={"height": "50px"},
                    ),
                    # Filters (on right side)
                    html.Div(
                        [
                            dcc.Dropdown(
                                options=[
                                    {"label": "Entity 1", "value": "entity1"},
                                    {"label": "Entity 2", "value": "entity2"},
                                ],
                                value="entity1",
                                style={
                                    "width": "150px",
                                    "minWidth": "120px",
                                    "marginRight": "0.5rem",
                                    "color": "white",
                                    "border": "none",
                                    "fontFamily": "Arial, sans-serif",
                                },
                            ),
                            dcc.Dropdown(
                                options=[
                                    {"label": "Scenario 1", "value": "scenario1"},
                                    {"label": "Scenario 2", "value": "scenario2"},
                                ],
                                value="scenario1",
                                style={
                                    "width": "150px",
                                    "minWidth": "120px",
                                    "color": "white",
                                    "border": "none",
                                    "fontFamily": "Arial, sans-serif",
                                },
                            ),
                        ],
                        style={"display": "flex", "flexWrap": "wrap", "gap": "0.5rem"},
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "1rem",
                    "backgroundColor": "#181b1d",
                    "boxShadow": "0 2px 4px rgba(0,0,0,0.2)",
                    "marginBottom": "2rem",
                    "fontFamily": "Arial, sans-serif",
                    "flexWrap": "wrap",
                    "gap": "1rem",
                },
            ),
            # KPIs
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H4("Current Balance"),
                                    html.H3(f"${data['current_balance']:,.0f}"),
                                    html.P(
                                        "+15% vs prev month", style={"color": "green"}
                                    ),
                                ],
                                style=kpi_box_style,
                            ),
                            html.Div(
                                [
                                    html.H4("Daily Avg In"),
                                    html.H3(f"${data['daily_avg_in']:,.0f}"),
                                    html.P(
                                        "+8% vs prev month", style={"color": "green"}
                                    ),
                                ],
                                style=kpi_box_style,
                            ),
                            html.Div(
                                [
                                    html.H4("Daily Avg Out"),
                                    html.H3(f"${data['daily_avg_out']:,.0f}"),
                                    html.P("-3% vs prev month", style={"color": "red"}),
                                ],
                                style=kpi_box_style,
                            ),
                            html.Div(
                                [
                                    html.H4("Liquidity Ratio"),
                                    html.H3(f"{data['liquidity_ratio']:.2f}"),
                                    html.P(
                                        "+5% vs prev month", style={"color": "green"}
                                    ),
                                ],
                                style=kpi_box_style,
                            ),
                            html.Div(
                                [
                                    html.H4("Pending Payments"),
                                    html.H3(f"${data['pending_payments']:,.0f}"),
                                    html.P(
                                        "+2% vs prev month", style={"color": "green"}
                                    ),
                                ],
                                style=kpi_box_style,
                            ),
                            html.Div(
                                [
                                    html.H4("Forecast Balance"),
                                    html.H3(f"${data['forecast_balance']:,.0f}"),
                                    html.P("+15% vs current", style={"color": "green"}),
                                ],
                                style=kpi_box_style,
                            ),
                        ],
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(250px, 1fr))",
                            "gap": "1rem",
                            "justifyContent": "center",
                            "marginBottom": "2rem",
                            "width": "100%",
                        },
                    ),
                    # Charts
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                figure=create_cash_flow_chart(data),
                                                style={
                                                    "height": "100%",
                                                    "width": "100%",
                                                },
                                            )
                                        ],
                                        style={
                                            **kpi_box_style,
                                            "margin": "0.5rem",
                                            "flex": "1 1 45%",
                                            "minWidth": "600px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                figure=create_balance_trend_chart(data),
                                                style={
                                                    "height": "100%",
                                                    "width": "100%",
                                                },
                                            )
                                        ],
                                        style={
                                            **kpi_box_style,
                                            "margin": "0.5rem",
                                            "flex": "1 1 45%",
                                            "minWidth": "600px",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "flexWrap": "wrap",
                                    "gap": "1rem",
                                    "marginBottom": "1rem",
                                    "width": "100%",
                                    "justifyContent": "space-between",
                                },
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                figure=create_daily_distribution_chart(
                                                    data
                                                ),
                                                style={
                                                    "height": "100%",
                                                    "width": "100%",
                                                },
                                            )
                                        ],
                                        style={
                                            **kpi_box_style,
                                            "margin": "0.5rem",
                                            "flex": "1 1 45%",
                                            "minWidth": "600px",
                                        },
                                    ),
                                    html.Div(
                                        [
                                            dcc.Graph(
                                                figure=create_forecast_chart(data),
                                                style={
                                                    "height": "100%",
                                                    "width": "100%",
                                                },
                                            )
                                        ],
                                        style={
                                            **kpi_box_style,
                                            "margin": "0.5rem",
                                            "flex": "1 1 45%",
                                            "minWidth": "600px",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "flexWrap": "wrap",
                                    "gap": "1rem",
                                    "width": "100%",
                                    "justifyContent": "space-between",
                                },
                            ),
                        ],
                        style={
                            "padding": "0 1rem",
                            "width": "100%",
                            "margin": "0 auto",
                        },
                    ),
                ],
                style={"padding": "0 2rem"},
            ),
        ],
        style={"fontFamily": "Arial, sans-serif"},
    )


# Create charts
def create_cash_flow_chart(data):
    fig = go.Figure()

    # Add Cash In bars
    fig.add_trace(
        go.Bar(x=data["dates"], y=data["cash_in"], name="Cash In", marker_color="green")
    )

    # Add Cash Out bars
    fig.add_trace(
        go.Bar(x=data["dates"], y=data["cash_out"], name="Cash Out", marker_color="red")
    )

    # Update layout
    fig.update_layout(
        title="Daily Cash Flow",
        height=500,
        barmode="group",
        bargap=0.15,
        bargroupgap=0.1,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="lightgrey"),
        yaxis=dict(showgrid=True, gridcolor="lightgrey"),
    )

    return fig


def create_balance_trend_chart(data):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data["dates"], y=data["balance"], name="Balance", line=dict(color="blue")
        )
    )
    fig.update_layout(
        title="Balance Trend",
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="lightgrey"),
        yaxis=dict(showgrid=True, gridcolor="lightgrey"),
    )
    return fig


def create_daily_distribution_chart(data):
    # Calculate components for waterfall chart
    components = {
        "Opening Balance": 1000000,  # Example starting balance
        "Customer Receipts": np.sum(data["cash_in"]),
        "Supplier Payments": -np.sum(
            data["cash_out"] * 0.6
        ),  # Assuming 60% is supplier payments
        "CAPEX": -np.sum(data["cash_out"] * 0.2),  # Assuming 20% is CAPEX
        "Bank Fees": -np.sum(data["cash_out"] * 0.05),  # Assuming 5% is bank fees
        "Loan Payments": -np.sum(
            data["cash_out"] * 0.15
        ),  # Assuming 15% is loan payments
    }

    # Calculate cumulative sum for waterfall
    cumulative = 0
    x_data = []
    y_data = []
    text = []

    for name, value in components.items():
        x_data.append(name)
        y_data.append(value)
        cumulative += value
        text.append(f"${value:,.0f}")

    # Add final balance
    x_data.append("Closing Balance")
    y_data.append(cumulative)
    text.append(f"${cumulative:,.0f}")

    # Create the waterfall chart
    fig = go.Figure()

    # Add bars
    fig.add_trace(
        go.Waterfall(
            name="Cash Flow",
            orientation="v",
            measure=["absolute"] + ["relative"] * (len(x_data) - 2) + ["total"],
            x=x_data,
            textposition="outside",
            text=text,
            y=y_data,
            connector={"line": {"color": "rgb(63, 63, 63)"}},
            decreasing={"marker": {"color": "red"}},
            increasing={"marker": {"color": "green"}},
            totals={"marker": {"color": "#3d3f41"}},
        )
    )

    # Update layout
    fig.update_layout(
        title="Cash Flow Waterfall",
        showlegend=False,
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(title="Amount ($)", showgrid=True, gridcolor="lightgrey"),
        xaxis=dict(title="Components", showgrid=True, gridcolor="lightgrey"),
    )

    return fig


def create_forecast_chart(data):
    # Create forecast data
    forecast_dates = pd.date_range(start=data["dates"][-1], periods=30, freq="D")
    forecast_values = np.linspace(data["balance"][-1], data["forecast_balance"], 30)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data["dates"],
            y=data["balance"],
            name="Historical",
            line=dict(color="blue"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast_dates,
            y=forecast_values,
            name="Forecast",
            line=dict(color="orange", dash="dash"),
        )
    )
    fig.update_layout(
        title="Balance Forecast",
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=True, gridcolor="lightgrey"),
        yaxis=dict(showgrid=True, gridcolor="lightgrey"),
    )
    return fig


# Set the layout
app.layout = create_layout()

if __name__ == "__main__":
    app.run_server(debug=True)
