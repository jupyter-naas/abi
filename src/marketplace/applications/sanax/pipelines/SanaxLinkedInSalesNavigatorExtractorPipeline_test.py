import pytest

from src.marketplace.applications.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
    SanaxLinkedInSalesNavigatorExtractorPipeline,
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration,
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters,
)
from src import services

@pytest.fixture
def pipeline() -> SanaxLinkedInSalesNavigatorExtractorPipeline:
    return SanaxLinkedInSalesNavigatorExtractorPipeline(
        configuration=SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
            triple_store=services.triple_store_service
        )
    )

def test_sanax_linkedin_sales_navigator_extractor_pipeline(pipeline: SanaxLinkedInSalesNavigatorExtractorPipeline):
    # Create test data
    import pandas as pd
    import os
    test_data = pd.DataFrame({
        'Name': ['John Smith', 'Jane Doe', 'Bob Wilson', 'John Johnson'],
        'Job Title': ['Executive Partner', 'CEO', 'CTO', 'Director'], 
        'Company': ['Example Corp', 'Tech Solutions', 'Global Systems', 'Acme Inc'],
        'Company URL': ['https://www.linkedin.com/company/example', 
                       'https://www.linkedin.com/company/techsolutions',
                       '',
                       'https://www.linkedin.com/company/acme'],
        'Location': ['New York, United States', 'London, United Kingdom', 
                    'Singapore', 'Toronto, Canada'],
        'Follows Your Company': ['No', 'Yes', 'No', 'Yes'],
        'Time in Role': ['1 year 1 month in role', '3 years 6 months in role',
                        '2 years 3 months in role', '5 years in role'],
        'Time in Company': ['1 year 1 month in company', '5 years in company',
                          '2 years 3 months in company', '7 years in company'],
        'LinkedIn URL': ['https://www.linkedin.com/sales/lead/example',
                        'https://www.linkedin.com/sales/lead/janedoe',
                        'https://www.linkedin.com/sales/lead/bobwilson',
                        'https://www.linkedin.com/sales/lead/johnjohnson']
    })

    # Save test data to datastore Excel file
    dir_path = os.path.join(SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration.data_store_path, "test")
    file_name = "test.xlsx"
    sheet_name = 'Sales Navigator Data'
    from src.utils.Storage import save_excel
    save_excel(test_data, dir_path, file_name, sheet_name)

    # Run pipeline with test data
    graph = pipeline.run(SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
        file_path=os.path.join(dir_path, file_name),
        sheet_name=sheet_name,
    ))

    # Validate graph is not empty
    assert len(graph) > 0, "Graph is empty"