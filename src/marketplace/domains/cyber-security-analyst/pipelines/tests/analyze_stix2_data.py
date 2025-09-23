import json
from collections import Counter
import os

def analyze_stix2_data(file_path):
    """
    Analyze a STIX2 JSON file and count the occurrences of each key and their values.
    
    Args:
        file_path (str): Path to the STIX2 JSON file
        
    Returns:
        tuple: (Counter for keys, dict mapping keys to their value counts)
    """
    # Load the JSON data
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Initialize counters for keys and values
    key_counter = Counter()
    value_counts = {}  # Dictionary to store Counter objects for each key's values
    
    # First count the top-level keys
    key_counter.update(data.keys())
    
    # Extract keys and values from each object in the "objects" array
    if 'objects' in data:
        print(f"Found {len(data['objects'])} objects in the file")
        for obj in data['objects']:
            # Recursively extract all keys and values
            extract_keys_and_values(obj, key_counter, value_counts)
    
    return key_counter, value_counts

def extract_keys_and_values(obj, key_counter, value_counts):
    """
    Recursively extract all keys and their values from an object and add them to the counters.
    
    Args:
        obj: The object to extract from (dict, list, or primitive value)
        key_counter (Counter): Counter to update with the keys
        value_counts (dict): Dictionary of Counters for values of each key
    """
    if isinstance(obj, dict):
        # Add all keys from this dictionary to the counter
        key_counter.update(obj.keys())
        
        # Count values for each key
        for key, value in obj.items():
            if key not in value_counts:
                value_counts[key] = Counter()
            
            # Only count primitive values (strings, numbers, booleans)
            if isinstance(value, (str, int, float, bool)):
                value_counts[key][str(value)] += 1
            
            # Recursively process all values
            extract_keys_and_values(value, key_counter, value_counts)
            
    elif isinstance(obj, list):
        # Recursively process all items in the list
        for item in obj:
            extract_keys_and_values(item, key_counter, value_counts)

def print_key_and_value_counts(key_counts, value_counts):
    """
    Print the key counts and their corresponding value distributions.
    
    Args:
        key_counts (Counter): Counter object with keys and their counts
        value_counts (dict): Dictionary of Counters for values of each key
    """
    print(f"{'Key':<30} | {'Count':<10} | Most Common Values")
    print("-" * 80)
    
    # Sort by count (descending) and then by key name (alphabetically)
    for key, count in sorted(key_counts.items(), key=lambda x: (-x[1], x[0])):
        # Get the top 3 most common values for this key
        if key == "type":
            most_common = value_counts.get(key, Counter()).most_common()
        else:
            most_common = value_counts.get(key, Counter()).most_common(3)
        value_str = ", ".join(f"{v}({c})" for v, c in most_common) if most_common else "N/A"
        print(f"{key:<30} | {count:<10} | {value_str}")

def main():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the path to the STIX2 file
    file_path = os.path.join(script_dir, "5869.pretty.stix2.json")
    
    # Analyze the file
    key_counts, value_counts = analyze_stix2_data(file_path)
    
    # Save key counts to JSON file
    output_path = os.path.join(script_dir, "key_counts.json")
    with open(output_path, 'w') as f:
        json.dump({
            'key_counts': dict(key_counts),
            'value_counts': {k: dict(v) for k, v in value_counts.items()}
        }, f, indent=4)
    
    print(f"\nResults saved to: {output_path}")
    print(f"\nTotal unique keys found: {len(key_counts)}")
    print_key_and_value_counts(key_counts, value_counts)

if __name__ == "__main__":
    main()
