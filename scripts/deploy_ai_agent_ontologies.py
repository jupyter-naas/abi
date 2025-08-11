#!/usr/bin/env python3
"""
Deploy AI Agent Ontologies to Module Directories

This script moves the generated AI agent ontologies from the storage directory
to their proper locations in each module's ontologies folder.

Usage:
    python scripts/deploy_ai_agent_ontologies.py
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

def get_latest_generation_summary():
    """Get the latest generation summary file."""
    storage_dir = Path("storage/datastore/core/modules/ai_agent_ontologies")
    
    if not storage_dir.exists():
        raise FileNotFoundError(f"Storage directory not found: {storage_dir}")
    
    summary_files = list(storage_dir.glob("generation_summary_*.json"))
    if not summary_files:
        raise FileNotFoundError(f"No summary files found in {storage_dir}")
    
    latest_summary = max(summary_files, key=lambda f: f.stat().st_mtime)
    
    with open(latest_summary, 'r', encoding='utf-8') as f:
        return json.load(f)

def deploy_ontologies():
    """Deploy ontologies to their respective module directories."""
    print("🚀 Deploying AI Agent Ontologies to Module Directories")
    
    # Load the latest generation summary
    try:
        summary = get_latest_generation_summary()
        print(f"📋 Found summary with {summary['agents_generated']} agents")
    except Exception as e:
        print(f"❌ Error loading summary: {e}")
        return False
    
    deployed_files = []
    
    for generated_file_path in summary['generated_files']:
        source_file = Path(generated_file_path)
        
        if not source_file.exists():
            print(f"⚠️  Source file not found: {source_file}")
            continue
        
        # Extract agent name from filename
        filename = source_file.name
        agent_name = filename.split('_')[0]  # e.g., "chatgpt" from "chatgpt_20250811T201531.ttl"
        
        # Determine target directory
        target_dir = Path(f"src/core/modules/{agent_name}/ontologies")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Create target filename with proper naming convention
        target_filename = f"AAModels_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.ttl"
        target_file = target_dir / target_filename
        
        # Copy file to target location
        try:
            shutil.copy2(source_file, target_file)
            deployed_files.append(target_file)
            print(f"📝 Deployed: {agent_name} → {target_file.relative_to(Path.cwd())}")
        except Exception as e:
            print(f"❌ Error deploying {agent_name}: {e}")
    
    # Generate deployment summary
    deployment_summary = {
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "source_summary": summary,
        "deployed_files": [str(f.relative_to(Path.cwd())) for f in deployed_files],
        "deployment_count": len(deployed_files)
    }
    
    summary_file = Path("storage/datastore/core/modules/ai_agent_ontologies") / f"deployment_summary_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(deployment_summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Deployment Complete!")
    print(f"📊 Summary:")
    print(f"   - {len(deployed_files)} ontology files deployed")
    print(f"   - Deployed to module ontologies directories")
    print(f"📋 Deployment summary: {summary_file}")
    
    return True

def main():
    success = deploy_ontologies()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
