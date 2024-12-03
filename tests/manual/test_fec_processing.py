from pathlib import Path
from integrations.fec import FECProcessor, FECConfig
import pandas as pd

def test_fec_processing():
    """Test FEC processing with template files"""
    
    # Configure FEC paths
    config = FECConfig(
        FEC_INPUT_PATH=Path("data/accounting/fec/inputs"),
        FEC_OUTPUT_PATH=Path("data/accounting/fec/outputs")
    )
    
    # Initialize processor
    processor = FECProcessor(config)
    
    # Process each file
    for file_path in config.FEC_INPUT_PATH.glob("*.txt"):
        print(f"\nProcessing {file_path.name}:")
        try:
            results = processor.process_file(file_path)
            print("✅ Processing successful")
            
            # Print summary statistics
            for report_type, df in results.items():
                if isinstance(df, pd.DataFrame):
                    print(f"\n{report_type.upper()} Summary:")
                    print(f"- Rows: {len(df)}")
                    print(f"- Columns: {list(df.columns)}")
                    
        except Exception as e:
            print(f"❌ Error processing file: {str(e)}")

if __name__ == "__main__":
    print("Starting FEC processing test...")
    test_fec_processing() 