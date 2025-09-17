#!/usr/bin/env python3
"""
Script to update config.yaml.example with all existing modules.

This module contains the functions to discover all modules and update the config.yaml.example file.
It can be used standalone or imported by other modules.

Usage: python scripts/update_config_example.py
"""

import sys
import os
from pathlib import Path
import yaml

# Module paths - should match the ones in src/__modules__.py
MODULE_PATH = [
    "src/core/modules",
    "src/custom/modules", 
    "src/marketplace/modules/applications",
    "src/marketplace/modules/domains"
]

def find_all_modules():
    """
    Find all module directories across all MODULE_PATH locations.
    
    Returns:
        list: List of module paths relative to project root
    """
    modules = []
    
    for modulepath in MODULE_PATH:
        module_base_path = Path(modulepath)
        
        if not module_base_path.exists():
            print(f"Warning: Module path does not exist: {modulepath}")
            continue
            
        print(f"Scanning {modulepath}...")
        
        # Get all directories in the module path
        for module in module_base_path.glob("*/"):
            if (
                module.is_dir()
                and module.name != "__pycache__"
                and not module.name.startswith('__')
                and "disabled" not in module.name
            ):
                # Add the full path relative to project root
                module_path = str(module)
                modules.append(module_path)
                print(f"  Found: {module_path}")
    
    return sorted(modules)


def update_config_example(config_path="config.yaml.example", silent=False):
    """
    Update config.yaml.example with all existing modules enabled.
    
    Args:
        config_path (str): Path to the config example file
        silent (bool): If True, suppress output messages
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not silent:
        print(f"Updating {config_path} with all existing modules...")
    
    # Find all modules across all MODULE_PATH locations
    all_modules = find_all_modules()
    
    if not all_modules:
        if not silent:
            print("No modules found")
        return False
    
    if not silent:
        print(f"\nTotal modules found: {len(all_modules)}")
    
    # Create new modules list with all modules enabled
    new_modules = []
    for module_path in all_modules:
        new_modules.append({
            'path': module_path,
            'enabled': True
        })
    
    # Write updated config back to file with proper formatting
    try:
        with open(config_path, 'w') as f:
            # Write config section
            f.write("config:\n")
            f.write("  workspace_id: # Naas workspace ID\n")
            f.write("  github_project_repository: # Github repository name (e.g. jupyter-naas/abi)\n")
            f.write("  github_support_repository: # Github repository name (e.g. jupyter-naas/abi)\n")
            f.write("  github_project_id: # Github project number stored in Github URL (e.g. https://github.com/jupyter-naas/abi/projects/1)\n")
            f.write('  triple_store_path: "storage/triplestore" # Path to the ontology store\n')
            f.write('  api_title: "ABI API" # API title\n')
            f.write('  api_description: "API for ABI, your Artifical Business Intelligence" # API description\n')
            f.write('  logo_path: "assets/logo.png" # Path to the logo\n')
            f.write('  favicon_path: "assets/favicon.ico" # Path to the favicon\n')
            f.write('  storage_name: "abi" # Name of the storage\n')
            f.write('  space_name: "abi" # Name of the space\n')
            f.write("\n")
            
            # Write modules section
            f.write("modules:\n")
            for module_data in new_modules:
                f.write(f'  - path: {module_data["path"]}\n')
                f.write(f'    enabled: {str(module_data["enabled"]).lower()}\n')
            f.write("  \n")
            
            # Write pipelines section
            f.write("pipelines:\n")
            f.write('  - name: github.GithubIssuesPipeline\n')
            f.write('    cron: "0 0 * * *"\n')
            f.write('    parameters:\n')
            f.write('      - github_repository: "https://github.com/jupyter-naas/abi"\n')
            f.write('      - github_repository: "https://github.com/jupyter-naas/docs"\n')
            f.write('      - github_repository: "https://github.com/jupyter-naas/naaspython"\n')
            
        if not silent:
            print(f"\nSuccessfully updated {config_path}")
            print(f"Added {len(new_modules)} modules with enabled: true")
        return True
    except Exception as e:
        if not silent:
            print(f"Error writing config file: {e}")
        return False


def main():
    """Main function to update config example."""
    print("Updating config.yaml.example with all existing modules...")
    print("=" * 55)
    
    # Run the update function
    success = update_config_example()
    
    if success:
        print("\n✅ Update completed successfully!")
        return 0
    else:
        print("\n❌ Update failed!")
        return 1


if __name__ == "__main__":
    exit(main())