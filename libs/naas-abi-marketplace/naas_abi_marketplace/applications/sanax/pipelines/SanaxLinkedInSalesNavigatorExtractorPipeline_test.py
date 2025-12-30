import pytest
from naas_abi import services
from naas_abi_marketplace.applications.sanax.pipelines.SanaxLinkedInSalesNavigatorExtractorPipeline import (
    SanaxLinkedInSalesNavigatorExtractorPipeline,
    SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration,
    SanaxLinkedInSalesNavigatorExtractorPipelineParameters,
)


@pytest.fixture
def pipeline() -> SanaxLinkedInSalesNavigatorExtractorPipeline:
    return SanaxLinkedInSalesNavigatorExtractorPipeline(
        configuration=SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration(
            triple_store=services.triple_store_service
        )
    )


def test_sanax_linkedin_sales_navigator_extractor_pipeline(
    pipeline: SanaxLinkedInSalesNavigatorExtractorPipeline,
):
    # Create test data
    import os

    import pandas as pd

    test_data = pd.DataFrame(
        [
            {
                "Name": "John Smith",
                "Job Title": "Executive Partner",
                "Company": "",
                "Company URL": "",
                "Location": "New York, United States",
                "Follows Your Company": "No",
                "Time in Role": "1 year 1 month in role",
                "Time in Company": "1 year 1 month in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/example",
            },
            {
                "Name": "Jane Doe",
                "Job Title": "CEO",
                "Company": "Tech Solutions",
                "Company URL": "https://www.linkedin.com/company/techsolutions",
                "Location": "London, United Kingdom",
                "Follows Your Company": "Yes",
                "Time in Role": "3 years 6 months in role",
                "Time in Company": "5 years in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/janedoe",
            },
            {
                "Name": "John Wilson",
                "Job Title": "CTO",
                "Company": "Global Systems",
                "Company URL": "",
                "Location": "Singapore",
                "Follows Your Company": "No",
                "Time in Role": "2 years 3 months in role",
                "Time in Company": "2 years 3 months in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/johnwilson",
            },
            {
                "Name": "Sarah Johnson",
                "Job Title": "VP of Sales",
                "Company": "Acme Corp",
                "Company URL": "https://www.linkedin.com/company/acmecorp",
                "Location": "Toronto, Canada",
                "Follows Your Company": "Yes",
                "Time in Role": "4 years 2 months in role",
                "Time in Company": "6 years in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/sarahjohnson",
            },
            {
                "Name": "Michael Chang",
                "Job Title": "Senior Developer",
                "Company": "Tech Innovators",
                "Company URL": "https://www.linkedin.com/company/techinnovators",
                "Location": "San Francisco, United States",
                "Follows Your Company": "No",
                "Time in Role": "2 years 8 months in role",
                "Time in Company": "2 years 8 months in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/michaelchang",
            },
            {
                "Name": "Emma Wilson",
                "Job Title": "Product Manager",
                "Company": "Digital Solutions",
                "Company URL": "https://www.linkedin.com/company/digitalsolutions",
                "Location": "Berlin, Germany",
                "Follows Your Company": "Yes",
                "Time in Role": "1 year 9 months in role",
                "Time in Company": "3 years in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/emmawilson",
            },
            {
                "Name": "David Kim",
                "Job Title": "Solutions Architect",
                "Company": "Cloud Systems",
                "Company URL": "https://www.linkedin.com/company/cloudsystems",
                "Location": "Seoul, South Korea",
                "Follows Your Company": "No",
                "Time in Role": "3 years 1 month in role",
                "Time in Company": "3 years 1 month in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/davidkim",
            },
            {
                "Name": "Lisa Chen",
                "Job Title": "Marketing Director",
                "Company": "Global Marketing",
                "Company URL": "https://www.linkedin.com/company/globalmarketing",
                "Location": "Sydney, Australia",
                "Follows Your Company": "Yes",
                "Time in Role": "2 years 5 months in role",
                "Time in Company": "4 years in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/lisachen",
            },
            {
                "Name": "Thomas Mueller",
                "Job Title": "Head of Engineering",
                "Company": "Software AG",
                "Company URL": "https://www.linkedin.com/company/softwareag",
                "Location": "Munich, Germany",
                "Follows Your Company": "No",
                "Time in Role": "3 years 8 months in role",
                "Time in Company": "5 years in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/thomasmueller",
            },
            {
                "Name": "Maria Garcia",
                "Job Title": "Business Development Manager",
                "Company": "Global Ventures",
                "Company URL": "https://www.linkedin.com/company/globalventures",
                "Location": "Madrid, Spain",
                "Follows Your Company": "Yes",
                "Time in Role": "1 year 11 months in role",
                "Time in Company": "1 year 11 months in company",
                "LinkedIn URL": "https://www.linkedin.com/sales/lead/mariagarcia",
            },
        ]
    )

    # Save test data to datastore Excel file
    dir_path = os.path.join(
        SanaxLinkedInSalesNavigatorExtractorPipelineConfiguration.data_store_path,
        "test",
    )
    file_name = "test.xlsx"
    sheet_name = "Sales Navigator Data"
    from naas_abi_core.utils.StorageUtils import StorageUtils
    from naas_abi_marketplace.applications.sanax import ABIModule

    storage_utils = StorageUtils(ABIModule.get_instance().engine.services.object_storage)
    storage_utils.save_excel(test_data, dir_path, file_name, sheet_name)

    # Run pipeline with test data
    graph = pipeline.run(
        SanaxLinkedInSalesNavigatorExtractorPipelineParameters(
            file_path=os.path.join(dir_path, file_name),
            sheet_name=sheet_name,
        )
    )

    # Validate graph is not empty
    assert len(graph) > 0, "Graph is empty"
