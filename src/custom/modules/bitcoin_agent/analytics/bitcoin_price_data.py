"""
Bitcoin Price Data Fetcher and Storage

A simple module to fetch Bitcoin price data from Yahoo Finance, 
store it in the datalake, and register in the triplestore.
"""

import os
import datetime
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from rdflib import Graph, Literal, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from typing import Optional, Dict, Any, List

# Define base paths
DATALAKE_PATH = "storage/datalake/bitcoin"
TRIPLESTORE_PATH = "storage/triplestore/analytics"

# Define namespaces
ABI = Namespace("http://ontology.naas.ai/abi/")

def fetch_bitcoin_price_data(period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch Bitcoin price data from Yahoo Finance.
    
    Args:
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        
    Returns:
        DataFrame with price data
    """
    # Fetch data
    ticker = 'BTC-USD'
    df = yf.download(ticker, period=period, interval=interval)
    
    # Reset index to make Date a column
    df = df.reset_index()
    
    # Rename Date column to timestamp for consistency
    df = df.rename(columns={'Date': 'timestamp'})
    
    return df

def store_bitcoin_data(df: pd.DataFrame, timestamp_str: Optional[str] = None) -> Dict[str, str]:
    """Store Bitcoin price data in datalake and triplestore.
    
    Args:
        df: DataFrame with price data
        timestamp_str: Optional timestamp string (default: current timestamp)
        
    Returns:
        Dictionary with file paths
    """
    # Create timestamp if not provided
    if timestamp_str is None:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Create directories
    datalake_dir = os.path.join(DATALAKE_PATH, timestamp_str)
    triplestore_dir = os.path.join(TRIPLESTORE_PATH, timestamp_str)
    
    os.makedirs(datalake_dir, exist_ok=True)
    os.makedirs(triplestore_dir, exist_ok=True)
    
    # Store CSV in datalake
    csv_path = os.path.join(datalake_dir, "bitcoin_price.csv")
    df.to_csv(csv_path, index=False)
    
    # Generate and store chart
    png_path = os.path.join(datalake_dir, "bitcoin_price_chart.png")
    generate_price_chart(df, png_path)
    
    # Generate and store TTL
    ttl_path = os.path.join(triplestore_dir, "bitcoin_price.ttl")
    graph = dataframe_to_rdf(df, timestamp_str)
    graph.serialize(destination=ttl_path, format="turtle")
    
    # Create metadata
    metadata = {
        "timestamp": timestamp_str,
        "csv_path": csv_path,
        "png_path": png_path,
        "ttl_path": ttl_path,
        "rows": len(df),
        "start_date": df["timestamp"].min().strftime("%Y-%m-%d") if not df.empty else None,
        "end_date": df["timestamp"].max().strftime("%Y-%m-%d") if not df.empty else None,
        "start_price": float(df["Close"].iloc[0]) if not df.empty else None,
        "end_price": float(df["Close"].iloc[-1]) if not df.empty else None,
        "price_change_pct": float((df["Close"].iloc[-1] - df["Close"].iloc[0]) / df["Close"].iloc[0] * 100) if not df.empty else None
    }
    
    # Store metadata as JSON
    metadata_path = os.path.join(datalake_dir, "metadata.json")
    import json
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return metadata

def generate_price_chart(df: pd.DataFrame, output_path: str) -> None:
    """Generate a price chart from the DataFrame.
    
    Args:
        df: DataFrame with price data
        output_path: Path to save the chart
    """
    # Extract data
    timestamps = df["timestamp"]
    close_prices = df["Close"]
    
    # Create figure and plot
    plt.figure(figsize=(12, 6))
    plt.style.use('ggplot')
    
    # Calculate price change
    price_change = close_prices.iloc[-1] - close_prices.iloc[0]
    color = 'green' if price_change >= 0 else 'red'
    
    # Plot line
    plt.plot(timestamps, close_prices, color=color, linewidth=2)
    
    # Add markers for start and end
    plt.scatter(timestamps.iloc[0], close_prices.iloc[0], color='blue', s=100, zorder=5)
    plt.scatter(timestamps.iloc[-1], close_prices.iloc[-1], color=color, s=100, zorder=5)
    
    # Format x-axis with dates
    if len(df) <= 30:  # For shorter time periods
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    else:
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    
    plt.gcf().autofmt_xdate()
    
    # Add grid
    plt.grid(True, alpha=0.3)
    
    # Add labels and title
    plt.xlabel('Date')
    plt.ylabel('Price (USD)')
    
    # Calculate change percentage
    change_pct = (price_change / close_prices.iloc[0]) * 100
    change_symbol = "+" if change_pct >= 0 else ""
    
    period_str = f"{len(df)} days" if len(df) > 1 else "24 hours"
    plt.title(f'Bitcoin Price - Last {period_str}\nCurrent: ${close_prices.iloc[-1]:,.2f} ({change_symbol}{change_pct:.2f}%)', fontsize=14)
    
    # Add annotations
    plt.annotate(f'${close_prices.iloc[0]:,.2f}', 
                 xy=(timestamps.iloc[0], close_prices.iloc[0]),
                 xytext=(-30, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=.2'))
    
    plt.annotate(f'${close_prices.iloc[-1]:,.2f}', 
                 xy=(timestamps.iloc[-1], close_prices.iloc[-1]),
                 xytext=(30, 20),
                 textcoords='offset points',
                 arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=.2'))
    
    # Save figure
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def dataframe_to_rdf(df: pd.DataFrame, timestamp_str: str) -> Graph:
    """Convert price DataFrame to RDF graph.
    
    Args:
        df: DataFrame with price data
        timestamp_str: Timestamp string for the dataset
        
    Returns:
        RDF Graph
    """
    # Create graph
    g = Graph()
    
    # Add prefixes
    g.bind("abi", ABI)
    g.bind("rdf", RDF)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)
    
    # Create dataset URI
    dataset_uri = URIRef(f"http://ontology.naas.ai/abi/analytics/bitcoin/pricedata/{timestamp_str}")
    
    # Add dataset metadata
    g.add((dataset_uri, RDF.type, ABI.BitcoinPriceDataset))
    g.add((dataset_uri, RDFS.label, Literal(f"Bitcoin Price Data - {timestamp_str}")))
    g.add((dataset_uri, ABI.timestamp, Literal(timestamp_str, datatype=XSD.string)))
    g.add((dataset_uri, ABI.rowCount, Literal(len(df), datatype=XSD.integer)))
    
    if not df.empty:
        # Add dataset date range
        g.add((dataset_uri, ABI.startDate, Literal(df["timestamp"].min().isoformat(), datatype=XSD.dateTime)))
        g.add((dataset_uri, ABI.endDate, Literal(df["timestamp"].max().isoformat(), datatype=XSD.dateTime)))
        
        # Add price stats
        g.add((dataset_uri, ABI.openPrice, Literal(float(df["Open"].iloc[0]), datatype=XSD.decimal)))
        g.add((dataset_uri, ABI.closePrice, Literal(float(df["Close"].iloc[-1]), datatype=XSD.decimal)))
        g.add((dataset_uri, ABI.highPrice, Literal(float(df["High"].max()), datatype=XSD.decimal)))
        g.add((dataset_uri, ABI.lowPrice, Literal(float(df["Low"].min()), datatype=XSD.decimal)))
        
        # Add price change
        price_change = float(df["Close"].iloc[-1] - df["Close"].iloc[0])
        price_change_pct = price_change / float(df["Close"].iloc[0]) * 100
        g.add((dataset_uri, ABI.priceChange, Literal(price_change, datatype=XSD.decimal)))
        g.add((dataset_uri, ABI.priceChangePct, Literal(price_change_pct, datatype=XSD.decimal)))
        
        # Add each data point
        for i, row in df.iterrows():
            point_uri = URIRef(f"http://ontology.naas.ai/abi/analytics/bitcoin/pricedata/{timestamp_str}/point/{i}")
            
            g.add((point_uri, RDF.type, ABI.BitcoinPricePoint))
            g.add((point_uri, ABI.inDataset, dataset_uri))
            g.add((point_uri, ABI.timestamp, Literal(row["timestamp"].isoformat(), datatype=XSD.dateTime)))
            g.add((point_uri, ABI.openPrice, Literal(float(row["Open"]), datatype=XSD.decimal)))
            g.add((point_uri, ABI.closePrice, Literal(float(row["Close"]), datatype=XSD.decimal)))
            g.add((point_uri, ABI.highPrice, Literal(float(row["High"]), datatype=XSD.decimal)))
            g.add((point_uri, ABI.lowPrice, Literal(float(row["Low"]), datatype=XSD.decimal)))
            g.add((point_uri, ABI.volume, Literal(float(row["Volume"]), datatype=XSD.decimal)))
    
    return g

def fetch_and_store_bitcoin_data(period: str = "1mo", interval: str = "1d") -> Dict[str, Any]:
    """Fetch Bitcoin price data and store it in the appropriate locations.
    
    Args:
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        
    Returns:
        Dictionary with metadata about the stored data
    """
    # Create timestamp
    timestamp_str = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Fetch data
    df = fetch_bitcoin_price_data(period, interval)
    
    # Store data
    metadata = store_bitcoin_data(df, timestamp_str)
    
    return metadata

def list_bitcoin_datasets() -> List[Dict[str, Any]]:
    """List all available Bitcoin price datasets.
    
    Returns:
        List of dataset metadata dictionaries
    """
    datasets = []
    
    # Check if datalake directory exists
    if not os.path.exists(DATALAKE_PATH):
        return datasets
    
    # Iterate through timestamp directories
    for timestamp_dir in os.listdir(DATALAKE_PATH):
        metadata_path = os.path.join(DATALAKE_PATH, timestamp_dir, "metadata.json")
        
        if os.path.exists(metadata_path):
            # Load metadata
            import json
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                datasets.append(metadata)
    
    # Sort by timestamp (newest first)
    datasets.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return datasets

if __name__ == "__main__":
    # Example usage
    metadata = fetch_and_store_bitcoin_data("1mo", "1d")
    print(f"Bitcoin price data stored:")
    print(f"  CSV: {metadata['csv_path']}")
    print(f"  PNG: {metadata['png_path']}")
    print(f"  TTL: {metadata['ttl_path']}")
    print(f"  Rows: {metadata['rows']}")
    print(f"  Date range: {metadata['start_date']} to {metadata['end_date']}")
    print(f"  Price: ${metadata['start_price']:.2f} to ${metadata['end_price']:.2f} ({metadata['price_change_pct']:.2f}%)") 