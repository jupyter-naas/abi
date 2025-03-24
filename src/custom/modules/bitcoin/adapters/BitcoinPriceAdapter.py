def format_bitcoin_price_response(price_data):
    """Format Bitcoin price data for display in the chat."""
    if "error" in price_data:
        return f"Sorry, I couldn't retrieve the Bitcoin price: {price_data['error']}"
    
    # Use the price_formatted field if available, otherwise format it ourselves
    if "price_formatted" in price_data:
        price_display = price_data["price_formatted"]
    else:
        # Ensure proper formatting if price_formatted isn't available
        price_display = f"{price_data['price']:,.2f}"
    
    source = price_data.get("source", "Unknown")
    currency = price_data.get("currency", "USD")
    
    return f"The current price of Bitcoin (BTC) is ${price_display} {currency} (Source: {source})" 