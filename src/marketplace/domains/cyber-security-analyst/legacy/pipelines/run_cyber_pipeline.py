#!/usr/bin/env python3
"""
Script to run the Cyber Security Event Data Pipeline

This script executes the pipeline to download and process cyber security events,
creating a structured dataset for agent interaction.
"""
# type: ignore

import sys
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Add the cyber-security-analyst module to path
module_dir = current_dir.parent.parent
sys.path.insert(0, str(module_dir))

# Import after path setup
from CyberEventDataPipeline import CyberEventDataPipeline  # noqa: E402

def main():
    """Run the cyber security event data pipeline."""
    print("🔒 Cyber Security Event Data Pipeline")
    print("=" * 50)
    
    # Set paths relative to the cyber-security-analyst module
    events_yaml_path = module_dir / "events.yaml"
    storage_base_path = Path("/Users/jrvmac/abi/storage/datastore/cyber")
    d3fend_ontology_path = module_dir / "legacy" / "ontologies" / "d3fend.ttl"
    
    print(f"📁 Events YAML: {events_yaml_path}")
    print(f"💾 Storage Path: {storage_base_path}")
    print(f"🧠 D3FEND Ontology: {d3fend_ontology_path}")
    print()
    
    # Check if events.yaml exists
    if not events_yaml_path.exists():
        print(f"❌ Error: Events YAML file not found at {events_yaml_path}")
        return 1
    
    # Initialize pipeline
    try:
        pipeline = CyberEventDataPipeline(
            events_yaml_path=str(events_yaml_path),
            storage_base_path=str(storage_base_path),
            d3fend_ontology_path=str(d3fend_ontology_path)
        )
        print("✅ Pipeline initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing pipeline: {e}")
        return 1
    
    # Run the pipeline
    try:
        print("\n🚀 Starting pipeline execution...")
        results = pipeline.run_pipeline()
        
        print("\n📊 Pipeline Results:")
        print(f"   Total Events: {results.get('total_events', 0)}")
        print(f"   Processed Successfully: {len(results.get('processed_events', []))}")
        print(f"   Failed: {len(results.get('failed_events', []))}")
        print(f"   Storage Location: {results.get('storage_base_path')}")
        
        # Show failed events if any
        failed_events = results.get('failed_events', [])
        if failed_events:
            print("\n⚠️  Failed Events:")
            for failed in failed_events:
                print(f"   - {failed.get('event_name', 'Unknown')}: {failed.get('error', 'Unknown error')}")
        
        # Create dataset summary
        print("\n📈 Creating dataset summary for agent interaction...")
        summary = pipeline.create_agent_dataset_summary()
        
        print("✅ Dataset summary created:")
        print(f"   Total Events: {summary['dataset_info']['total_events']}")
        print(f"   Categories: {len(summary['event_categories'])}")
        print(f"   Affected Sectors: {len(summary['affected_sectors'])}")
        print(f"   Attack Vectors: {len(summary['attack_vectors'])}")
        print(f"   D3FEND Techniques: {len(summary['d3fend_techniques'])}")
        
        print("\n🎉 Pipeline completed successfully!")
        print(f"📂 Data available at: {storage_base_path}")
        print("🤖 Dataset is ready for agent interaction!")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error running pipeline: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
