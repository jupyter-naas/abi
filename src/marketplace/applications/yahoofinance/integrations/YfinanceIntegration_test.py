import pytest

from src.marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
    YfinanceIntegration,
    YfinanceIntegrationConfiguration
)
import pandas as pd

@pytest.fixture
def integration() -> YfinanceIntegration:
    configuration = YfinanceIntegrationConfiguration()
    return YfinanceIntegration(configuration)

def test_get_ticker_info(integration: YfinanceIntegration):
    """Test get_ticker_info method with MSFT ticker."""
    result = integration.get_ticker_info("MSFT")
    
    # Validate result structure and content
    assert result is not None
    assert isinstance(result, dict)
    
    # Check essential ticker info fields
    assert "symbol" in result
    assert "longName" in result or "shortName" in result
    assert "sector" in result
    assert "industry" in result
    assert "marketCap" in result
    
    # Validate specific MSFT data
    assert result["symbol"] == "MSFT"
    assert result["sector"] == "Technology"
    assert result["industry"] == "Software - Infrastructure"
    assert "Microsoft" in result.get("longName", "") or "Microsoft" in result.get("shortName", "")

def test_get_ticker_history(integration: YfinanceIntegration):
    """Test get_ticker_history method with MSFT ticker for 1 month period."""
    result = integration.get_ticker_history("MSFT", "1mo")
    
    # Validate result structure
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    
    # Check first record structure
    first_record = result[0]
    assert isinstance(first_record, dict)
    
    # Validate OHLCV data structure
    required_fields = ["key", "open", "high", "low", "close", "volume"]
    for field in required_fields:
        assert field in first_record, f"Missing field: {field}"
    
    # Validate data types
    assert isinstance(first_record["open"], (int, float))
    assert isinstance(first_record["high"], (int, float))
    assert isinstance(first_record["low"], (int, float))
    assert isinstance(first_record["close"], (int, float))
    assert isinstance(first_record["volume"], (int, float))
    
    # Validate OHLC relationships
    assert first_record["high"] >= first_record["open"]
    assert first_record["high"] >= first_record["close"]
    assert first_record["low"] <= first_record["open"]
    assert first_record["low"] <= first_record["close"]

def test_get_ticker_financials(integration: YfinanceIntegration):
    """Test get_ticker_financials method with MSFT ticker."""
    result = integration.get_ticker_financials("MSFT")
    
    # Validate result structure
    assert result is not None
    assert isinstance(result, dict)
    
    # Check expected financial data sections
    expected_sections = ["quarterly_income_stmt", "calendar", "analyst_price_targets"]
    for section in expected_sections:
        assert section in result, f"Missing section: {section}"
    
    # Validate quarterly income statement
    quarterly_stmt = result["quarterly_income_stmt"]
    assert isinstance(quarterly_stmt, list)
    
    if len(quarterly_stmt) > 0:
        # Check structure of financial statement record
        stmt_record = quarterly_stmt[0]
        assert isinstance(stmt_record, dict)
        assert "key" in stmt_record  # Should have date key
    
    # Validate calendar data
    calendar = result["calendar"]
    assert isinstance(calendar, list)
    
    # Validate analyst price targets
    analyst_targets = result["analyst_price_targets"]
    assert isinstance(analyst_targets, dict)

def test_get_sector_info(integration: YfinanceIntegration):
    """Test get_sector_info method with financial-services sector."""
    result = integration.get_sector_info("financial-services")
    
    # Validate result structure
    assert result is not None
    assert isinstance(result, dict)
    
    # Check essential sector info fields
    required_fields = ["key", "name", "symbol", "ticker", "overview", "top_companies", "industries"]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"
    
    # Validate specific sector data
    assert result["key"] == "financial-services"
    assert result["name"] == "Financial Services"
    assert result["symbol"] == "^YH103"
    
    # Validate ticker info
    assert isinstance(result["ticker"], dict)
    
    # Validate top companies
    top_companies = result["top_companies"]
    assert isinstance(top_companies, list)
    
    # Validate industries
    industries = result["industries"]
    assert isinstance(industries, list)

def test_get_industry_info(integration: YfinanceIntegration):
    """Test get_industry_info method with railroads industry."""
    result = integration.get_industry_info("railroads")
    
    # Validate result structure
    assert result is not None
    assert isinstance(result, dict)
    
    # Check essential industry info fields
    required_fields = ["sector_key", "sector_name", "top_performing_companies", "top_growth_companies"]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"
    
    # Validate sector information
    assert isinstance(result["sector_key"], str)
    assert isinstance(result["sector_name"], str)
    
    # Validate company lists
    top_performing = result["top_performing_companies"]
    top_growth = result["top_growth_companies"]
    
    assert isinstance(top_performing, list)
    assert isinstance(top_growth, list)
    
    # If companies exist, validate structure
    if len(top_performing) > 0:
        company = top_performing[0]
        assert isinstance(company, dict)
        assert "key" in company  # Should have company identifier

def test_search_ticker(integration: YfinanceIntegration):
    """Test search_ticker method with Microsoft company search."""
    result = integration.search_ticker("Microsoft")
    
    # Validate result structure
    assert result is not None
    assert isinstance(result, list)
    
    # Should find Microsoft-related results
    assert len(result) > 0
    
    # Check structure of search results
    first_result = result[0]
    assert isinstance(first_result, dict)
    
    # Common search result fields
    expected_fields = ["symbol", "shortname", "longname", "exchDisp"]
    found_fields = [field for field in expected_fields if field in first_result]
    assert len(found_fields) > 0, "Search result should contain at least one expected field"
    
    # Should find MSFT in results
    msft_found = any(
        result_item.get("symbol") == "MSFT" 
        for result_item in result
    )
    assert msft_found, "Microsoft search should return MSFT symbol"

def test_integration_configuration():
    """Test YfinanceIntegrationConfiguration default values."""
    config = YfinanceIntegrationConfiguration()
    
    assert config.data_store_path == "datastore/yahoofinance/yfinance"
    
    # Test custom configuration
    custom_config = YfinanceIntegrationConfiguration(
        data_store_path="custom/path/yahoofinance"
    )
    assert custom_config.data_store_path == "custom/path/yahoofinance"

def test_data_conversion_methods(integration: YfinanceIntegration):
    """Test internal data conversion methods."""    
    # Test _result_df_to_dict with sample DataFrame
    sample_data = {
        'Open': [100.0, 101.0],
        'Close': [102.0, 103.0],
        'Volume': [1000, 1100]
    }
    df = pd.DataFrame(sample_data, index=pd.date_range('2023-01-01', periods=2))
    
    result = integration._result_df_to_dict(df)
    
    assert isinstance(result, list)
    assert len(result) == 2
    assert 'key' in result[0]  # Should have index as key
    assert 'open' in result[0]  # Column names should be lowercase
    assert 'close' in result[0]
    assert 'volume' in result[0]
    
    # Test _convert_list with timestamps
    test_list = [pd.Timestamp('2023-01-01'), None, 'regular_string', 123]
    converted = integration._convert_list(test_list)
    
    assert len(converted) == 4
    assert isinstance(converted[0], str)  # Timestamp converted to string
    assert converted[1] is None  # None preserved
    assert converted[2] == 'regular_string'  # String preserved
    assert converted[3] == 123  # Number preserved