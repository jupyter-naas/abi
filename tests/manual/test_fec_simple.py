from pathlib import Path
from integrations.fec import FECProcessor, FECConfig
import pandas as pd

def test_simple():
    # Create test data
    df = pd.DataFrame({
        'JournalCode': ['VE', 'AC'],
        'CompteNum': ['411000', '401000'],
        'Debit': [1000.0, 0.0],
        'Credit': [0.0, 1000.0]
    })
    
    # Save test file
    Path("data/accounting/fec/inputs").mkdir(parents=True, exist_ok=True)
    test_file = Path("data/accounting/fec/inputs/test.txt")
    df.to_csv(test_file, sep='|', index=False)
    
    # Process
    processor = FECProcessor()
    result = processor.process_file(test_file)
    
    print("✅ Test successful" if len(result["data"]) == 2 else "❌ Test failed")

if __name__ == "__main__":
    test_simple() 