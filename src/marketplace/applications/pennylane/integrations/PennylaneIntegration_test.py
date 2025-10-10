import pytest
from datetime import datetime, timedelta

from src import secret
from src.marketplace.applications.pennylane.integrations.PennylaneIntegration import (
    PennylaneIntegration, 
    PennylaneIntegrationConfiguration
)
from abi import logger

@pytest.fixture(params=['PENNYLANE_API_TOKEN_FLEXOFFICE', 'PENNYLANE_API_TOKEN_VLRT'])
def pennylane_integration(request) -> PennylaneIntegration:
    configuration = PennylaneIntegrationConfiguration(
        api_key=secret.get(request.param)
    )
    return PennylaneIntegration(configuration)

def test_list_customers(pennylane_integration: PennylaneIntegration):
    customers = pennylane_integration.list_customers()

    assert len(customers) > 0, f"Expected more than 0 customers, got {len(customers)}"
    logger.info(f"Total customers: {len(customers)}")
    logger.info(f"Customers: {customers[0]}")

def test_list_customer_invoices(pennylane_integration: PennylaneIntegration):
    customer_invoices = pennylane_integration.list_customer_invoices()

    assert len(customer_invoices) > 0, f"Expected more than 0 customer invoices, got {len(customer_invoices)}"
    logger.info(f"Total customer invoices: {len(customer_invoices)}")
    logger.info(f"Customer invoices: {customer_invoices[0]}")

def test_list_customer_invoices_with_filters(pennylane_integration: PennylaneIntegration):
    start_date = (datetime.now() + timedelta(days=365*2)).strftime('%Y-%m-%d')
    logger.info(f"Start date: {start_date}")
    customer_invoices = pennylane_integration.list_customer_invoices(start_date=start_date)

    assert len(customer_invoices) == 0, f"Expected 0 customer invoices, got {len(customer_invoices)}"

def test_list_categories(pennylane_integration: PennylaneIntegration):
    categories = pennylane_integration.list_categories()

    assert len(categories) > 0, f"Expected more than 0 categories, got {len(categories)}"
    logger.info(f"Total categories: {len(categories)}")
    logger.info(f"Categories: {categories[0]}")