#!/usr/bin/env python3
"""
Utility to verify Bitcoin price storage
"""
import os
import json
import sys

def verify_storage():
    """Verify if Bitcoin price storage files exist and are accessible."""
    
    # Try multiple possible storage paths
    storage_paths = [
        "/storage/datastore/bitcoin/prices",
        "/app/data/bitcoin/prices",
        os.path.join(os.path.expanduser("~"), "bitcoin_data/prices")
    ]
    
    print("Bitcoin Price Storage Verification")
    print("==================================")
    
    found_files = False
    
    for path in storage_paths:
        print(f"\nChecking path: {path}")
        if not os.path.exists(path):
            print(f"  ❌ Path does not exist")
            continue
            
        print(f"  ✅ Path exists")
        print(f"  - Directory permissions: {oct(os.stat(path).st_mode)[-3:]}")
        
        # List files in directory
        try:
            files = [f for f in os.listdir(path) if f.endswith('.json')]
            print(f"  - Found {len(files)} JSON files")
            
            if files:
                found_files = True
                
                # Check a sample file
                sample_file = os.path.join(path, files[0])
                file_size = os.path.getsize(sample_file)
                print(f"  - Sample file: {files[0]} ({file_size} bytes)")
                
                # Try to read the file
                try:
                    with open(sample_file, 'r') as f:
                        data = json.load(f)
                    print(f"  - File is readable and contains {len(data)} records")
                    
                    # Print a sample record
                    if data:
                        print(f"  - Sample record: {json.dumps(data[0])[:100]}...")
                except Exception as e:
                    print(f"  ❌ Error reading file: {e}")
        except Exception as e:
            print(f"  ❌ Error listing directory: {e}")
    
    if not found_files:
        print("\n❌ NO BITCOIN PRICE DATA FILES FOUND in any expected location")
        
        # Check if we can create a test file in the storage directory
        test_path = "/storage/datastore/bitcoin/prices"
        if not os.path.exists(test_path):
            try:
                os.makedirs(test_path, exist_ok=True)
                print(f"Created directory: {test_path}")
            except Exception as e:
                print(f"❌ Could not create directory {test_path}: {e}")
                
        # Try to create a test file
        test_file = os.path.join(test_path, "storage_test.txt")
        try:
            with open(test_file, 'w') as f:
                f.write("Storage test")
            print(f"✅ Successfully created test file: {test_file}")
            # Read back the test file
            with open(test_file, 'r') as f:
                content = f.read()
            print(f"✅ Successfully read test file, content: {content}")
        except Exception as e:
            print(f"❌ Failed to create/read test file: {e}")
    
    return found_files

if __name__ == "__main__":
    success = verify_storage()
    sys.exit(0 if success else 1) 