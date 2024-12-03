import pytest
from pathlib import Path
import pandas as pd
from integrations.fec import FECProcessor, FECConfig

@pytest.fixture
def test_config():
    return FECConfig(
        FEC_INPUT_PATH=Path("tests/data/fec/input"),
        FEC_OUTPUT_PATH=Path("tests/data/fec/output")
    )

@pytest.fixture
def sample_fec_data():
    return pd.DataFrame({
        'JournalCode': ['VE', 'AC'],
        'CompteNum': ['411000', '401000'],
        'Debit': [1000.0, 0.0],
        'Credit': [0.0, 1000.0]
    })

def test_process_file(test_config, sample_fec_data, tmp_path):
    processor = FECProcessor(test_config)
    input_file = tmp_path / "test.txt"
    sample_fec_data.to_csv(input_file, sep='|', index=False)
    
    result = processor.process_file(input_file)
    assert "data" in result
    assert isinstance(result["data"], pd.DataFrame)
    