import pytest

from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.FilesIngestionPipeline import (
    FilesIngestionPipeline,
)


@pytest.mark.parametrize(
    ("input_path", "object_key", "output_path", "expected_destination_path"),
    [
        (
            "file_ingestion/input",
            "file_ingestion/input/a/b/file.pdf",
            "file_ingestion/output",
            "file_ingestion/output/a/b",
        ),
        (
            "file_ingestion/input/",
            "file_ingestion/input/a/b/file.pdf",
            "file_ingestion/output",
            "file_ingestion/output/a/b",
        ),
    ],
)
def test_build_destination_path_keeps_output_prefix(
    input_path: str,
    object_key: str,
    output_path: str,
    expected_destination_path: str,
):
    destination_path = FilesIngestionPipeline._build_destination_path(
        input_path=input_path,
        output_path=output_path,
        object_key=object_key,
    )

    assert destination_path == expected_destination_path
    assert destination_path.startswith(output_path)
