import pytest

from src.marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    LinkedInExportIntegration,
    LinkedInExportIntegrationConfiguration
)

@pytest.fixture
def integration() -> LinkedInExportIntegration:
    export_file_path = "storage/datastore/linkedin/export/florent-ravenel/Complete_LinkedInDataExport_11-06-2025.zip (1).zip"
    configuration = LinkedInExportIntegrationConfiguration(export_file_path=export_file_path)
    return LinkedInExportIntegration(configuration)


def test_unzip_export(integration: LinkedInExportIntegration):
    result = integration.unzip_export()
    assert result is not None, result
    assert result["extracted_directory"] is not None, result
    assert result["files_count"] is not None, result
    assert result["folders_count"] is not None, result
    assert result["files"] is not None, result
    assert result["folders"] is not None, result


def test_list_files_and_folders(integration: LinkedInExportIntegration):
    result = integration.list_files_and_folders()
    assert result is not None, result
    assert result["files"] is not None, result
    assert result["folders"] is not None, result
    assert result["total_files"] is not None, result
    assert result["total_folders"] is not None, result
    assert result["path"] is not None, result

def test_list_files(integration: LinkedInExportIntegration):
    result = integration.list_files()
    assert result is not None, result
    assert len(result) > 0, result

def test_read_csv(integration: LinkedInExportIntegration):  
    df = integration.read_csv(csv_file_name="Connections.csv")
    assert df is not None, df
    assert len(df) > 0, df