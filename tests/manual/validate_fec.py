from pathlib import Path
import pandas as pd
from integrations.fec import FECProcessor, FECConfig

def validate_fec_integration():
    """Validate FEC integration with sample data"""
    print("🔍 Starting FEC integration validation...")
    
    # 1. Setup directories
    config = FECConfig(
        FEC_INPUT_PATH=Path("data/accounting/fec/inputs"),
        FEC_OUTPUT_PATH=Path("data/accounting/fec/outputs")
    )
    
    config.FEC_INPUT_PATH.mkdir(parents=True, exist_ok=True)
    config.FEC_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    
    # 2. Create sample FEC file
    sample_data = pd.DataFrame({
        'JournalCode': ['VE', 'AC', 'BQ'],
        'JournalLib': ['Ventes', 'Achats', 'Banque'],
        'EcritureNum': ['VE001', 'AC001', 'BQ001'],
        'EcritureDate': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'CompteNum': ['411000', '401000', '512000'],
        'CompteLib': ['Clients', 'Fournisseurs', 'Banque'],
        'Debit': [1000.0, 0.0, 0.0],
        'Credit': [0.0, 500.0, 500.0]
    })
    
    sample_file = config.FEC_INPUT_PATH / "sample_fec.txt"
    sample_data.to_csv(sample_file, sep='|', index=False)
    print(f"✅ Created sample FEC file: {sample_file}")
    
    # 3. Process the file
    processor = FECProcessor(config)
    try:
        result = processor.process_file(sample_file)
        print("✅ File processed successfully")
        
        # 4. Validate results
        processed_df = result['data']
        print("\n📊 Validation Results:")
        print(f"- Rows processed: {len(processed_df)}")
        print(f"- Columns: {list(processed_df.columns)}")
        print("\nSample of processed data:")
        print(processed_df.head(2).to_string())
        
        # 5. Check output files
        output_files = list(config.FEC_OUTPUT_PATH.glob("*.parquet"))
        print(f"\n💾 Output files generated: {len(output_files)}")
        for f in output_files:
            print(f"- {f.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during processing: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting FEC validation...\n")
    success = validate_fec_integration()
    print(f"\nValidation {'succeeded' if success else 'failed'} ✨") 