from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src import secret, config, services
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from abi import logger
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from datetime import datetime, timedelta
import pandas as pd
from typing import Tuple
from src.core.modules.common.integrations.NaasIntegration import NaasIntegration, NaasIntegrationConfiguration
from src.marketplace.modules.trading.integrations.YahooFinanceIntegration import YahooFinanceIntegration, YahooFinanceIntegrationConfiguration
import os
import plotly.graph_objects as go
import io

@dataclass
class StockPriceAnalysisWorkflowConfiguration(WorkflowConfiguration):
    """Configuration for StockPriceAnalysis workflow.
    
    Attributes:
        integration_config (NaasIntegrationConfiguration): Configuration for the Naas integration
    """
    yahoo_finance_integration_config: YahooFinanceIntegrationConfiguration
    naas_integration_config: NaasIntegrationConfiguration
    datastore_path: str = "datastore/trading/stock_price_analysis"

class StockPriceAnalysisWorkflowParameters(WorkflowParameters):
    """Parameters for StockPriceAnalysis workflow execution.
    
    Attributes:
        start_date (str): Start date for earnings calendar in YYYY-MM-DD format. Defaults to today.
        end_date (str): End date for earnings calendar in YYYY-MM-DD format. Defaults to 7 days from start_date.
        ticker (Optional[str]): Optional specific stock ticker to filter for (e.g., 'AAPL')
    """
    symbol: str = Field(description="The stock symbol to analyze, e.g. 'AAPL'. Use your internal knowledge to find the correct symbol.")

class StockPriceAnalysisWorkflow(Workflow):
    """Workflow for retrieving company earnings calendar from Yahoo Finance.
    
    This workflow provides methods to extract upcoming earnings release dates
    for companies in a specified date range.
    """
    
    __configuration: StockPriceAnalysisWorkflowConfiguration
    
    def __init__(self, configuration: StockPriceAnalysisWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self._naas_integration = NaasIntegration(self.__configuration.naas_integration_config)
        self._yahoo_finance_integration = YahooFinanceIntegration(self.__configuration.yahoo_finance_integration_config)
        
    def __init_workflow(self, symbol: str):
        self.__symbol = symbol
        self.__output_dir = os.path.join(self.__configuration.datastore_path, symbol)
        self.__filename = f"{datetime.now().strftime('%Y%m%d')}_stock_price_analysis_{symbol}.png"

    def __prep_earnings_data(self) -> List[Dict[str, Any]]:
        # Get earnings calendar
        data = self._yahoo_finance_integration.get_earnings_calls(self.__symbol)
        earnings_df = pd.read_csv(io.BytesIO(data))

        # Format date
        earnings_df['Earnings Date'] = pd.to_datetime(earnings_df['Earnings Date'].str.split('at').str[0])

        # Get closest earnings date
        today = pd.Timestamp.now()
        earnings_df['date_diff'] = abs(earnings_df['Earnings Date'] - today)
        closest_date_idx = earnings_df['date_diff'].idxmin()
        
        # Drop date diff column
        earnings_df = earnings_df.drop('date_diff', axis=1)

        # Get earnings data for the last 12 months
        earnings_df = earnings_df[closest_date_idx-1:]
        return earnings_df.reset_index(drop=True)

    def __prep_stock_data(self, period1: int, period2: int, frequency: str) -> pd.DataFrame:
        # Get historical data
        data = self._yahoo_finance_integration.get_historical_data(self.__symbol, period1, period2, frequency)
        df = pd.read_csv(io.BytesIO(data))

        # Enforce headers
        df.columns = ['Index', 'Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']

        # Format date
        df['Date'] = pd.to_datetime(df['Date'])

        # Filter out dividend rows
        df = df[~df['Close'].astype(str).str.contains('Dividend|Stock Splits', na=False)]

        # Sort by date
        df = df.sort_values('Date')

        # Convert close to float
        df['Close'] = df['Close'].astype(float)
        
        # Calculate moving averages
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        return df.reset_index(drop=True)

    def __create_earnings_text(self, earnings_df: pd.DataFrame) -> str:
        # Get next earnings info
        next_earnings = earnings_df['Earnings Date'].iloc[0]
        days_until = (next_earnings - pd.Timestamp.now()).days
        next_earnings_str = next_earnings.strftime('%Y-%m-%d')
        earnings_text = f"<span style='font-size: 14px'>Next Earning Call: {next_earnings_str} (in {days_until} days)</span>"
        return earnings_text
    
    def __create_price_variation_text(self, df: pd.DataFrame) -> tuple[str, dict[str, tuple[str, str]]]:
        """Calculate and format price variations for different time periods."""
        # Daily variation
        last_date = df['Date'].iloc[-1]
        last_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        daily_diff = last_price - prev_price
        daily_diff_pct = (daily_diff / prev_price) * 100
        
        daily_variation_color = 'red' if daily_diff < 0 else 'green'
        daily_variation_text = f"<span style='font-size: 15px;font-weight: bold'>{last_price:.2f} <span style='font-size: 14px; color: {daily_variation_color}'>{daily_diff:+.2f} ({daily_diff_pct:+.2f}%)</span></span><span style='font-size: 12px'> at close: {last_date.strftime('%Y-%m-%d')}</span>"

        # Calculate variations for different periods
        period_variations = {}
        periods = {
            'Week': 5,  # Trading days
            'Month': 21,  # Approximate trading days
            'Year': 252  # Approximate trading days
        }

        for period_name, days in periods.items():
            if len(df) > days:
                period_price = df['Close'].iloc[-days-1]
                period_diff = last_price - period_price
                period_diff_pct = (period_diff / period_price) * 100
                period_color = 'red' if period_diff < 0 else 'green'
                period_text = f"{period_diff_pct:+.2f}%"
                period_variations[period_name] = (period_text, period_color)
            else:
                period_variations[period_name] = ("N/A", 'gray')

        return daily_variation_text, period_variations
        
    def __create_analysis_chart(
            self, 
            df: pd.DataFrame, 
            earnings_df_chart: pd.DataFrame, 
            title: str, 
            period_variations: dict[str, tuple[str, str]]
        ) -> go.Figure:        
        # Create chart
        fig = go.Figure()
        
        # Add price line
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name='Close Price',
        ))
        
        # Add moving averages
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['MA20'],
            mode='lines',
            name='MA20',
            line=dict(dash='dot')
        ))
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['MA50'],
            mode='lines',
            name='MA50',
            line=dict(dash='dot')
        ))
        
        # Add earnings markers
        fig.add_trace(go.Scatter(
            x=earnings_df_chart['Date'],
            y=earnings_df_chart['Close'],
            mode='markers',
            marker=dict(size=12, symbol='star', color='gold'),
            name='Earning Call Date'
        ))
        
        # Create period variations text
        periods_text = " ".join([
            f"vs {period}: <span style='color: {color}'>{text}</span>"
            for period, (text, color) in period_variations.items()
        ])
        
        # Update layout
        fig.update_layout(
            title={
                'text': title,
                'x': 0.5,
                'y': 0.95,
                'xanchor': 'center',
                'yanchor': 'top'
            },
            annotations=[
                {
                    'text': periods_text,
                    'x': 0,
                    'y': 0.95,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'xanchor': 'left',
                    'yanchor': 'bottom',
                    'font': {'size': 14}
                },
                {
                    'text': f"Source: YahooFinance extracted at {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    'x': 0,
                    'y': -0.15,
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'xanchor': 'left',
                    'yanchor': 'top',
                    'font': {'size': 10, 'color': 'gray'}
                }
            ],
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode='x unified',
            margin=dict(b=120),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        return fig

    def get_stock_price_analysis(self, parameters: StockPriceAnalysisWorkflowParameters) -> str:
        """Get stock price analysis from Yahoo Finance.
        
        Args:
            parameters (StockPriceAnalysisWorkflowParameters): Parameters for the workflow
            
        Returns:
            str: URL of the generated analysis chart
        """
        # Initialize workflow
        self.__init_workflow(parameters.symbol)

        # Get earnings data
        earnings_df = self.__prep_earnings_data()

        # Get company name
        company_name = earnings_df['Company'].iloc[0]

        # Create earnings text
        earnings_text = self.__create_earnings_text(earnings_df)
        
        # Get stock data
        period1 = int((datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=380)).timestamp())
        period2 = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        frequency = "1d"
        stock_df = self.__prep_stock_data(period1, period2, frequency)

        # Calculate variations
        variation_text, period_variations = self.__create_price_variation_text(stock_df)

        # Create title
        title = f"<span style='font-size: 20px; font-weight: bold'>{company_name} ({parameters.symbol})</span><br>{variation_text}<br>{earnings_text}"
        
        # Create and save chart
        earnings_df_chart = stock_df[stock_df['Date'].isin(earnings_df['Earnings Date'])].reset_index(drop=True)
        fig = self.__create_analysis_chart(stock_df, earnings_df_chart, title, period_variations)
        
        # Save stock data
        services.storage_service.put_object(
            prefix=self.__output_dir,
            key=f"{datetime.now().strftime('%Y%m%d')}_stock_price_analysis_{parameters.symbol}_stock_data.csv",
            content=stock_df.to_csv(index=False).encode('utf-8'),
        )

        # Save earnings data
        services.storage_service.put_object(
            prefix=self.__output_dir,
            key=f"{datetime.now().strftime('%Y%m%d')}_stock_price_analysis_{parameters.symbol}_earnings_data.csv",
            content=earnings_df.to_csv(index=False).encode('utf-8'),
        )
        
        # Save chart to file
        services.storage_service.put_object(
            prefix=self.__output_dir,
            key=self.__filename,
            content=fig.to_image(format="png", height=800, width=1200),
        )
        
        # Upload to storage
        asset = self._naas_integration.upload_asset(
            data=fig.to_image(format="png", height=800, width=1200),
            workspace_id=config.workspace_id,
            storage_name=config.storage_name,
            prefix=self.__output_dir,
            object_name=self.__filename
        )
        asset_url = asset.get("asset").get("url")
        if asset_url.endswith("/"):
            asset_url = asset_url[:-1]

        return {
            "symbol": parameters.symbol,
            "company_name": company_name,
            "chart_url": asset_url,
            "stock_data": stock_df.to_dict(orient="records"),
            "earnings_data": earnings_df.to_dict(orient="records")
        }
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="trading-get_stock_price_analysis",
                description="Get stock price data with a chart with the next earnings call date and price variations and the data used to generate the chart from Yahoo Finance.",
                func=lambda **kwargs: self.get_stock_price_analysis(StockPriceAnalysisWorkflowParameters(**kwargs)),
                args_schema=StockPriceAnalysisWorkflowParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass