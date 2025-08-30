#!/usr/bin/env python3
"""
AI Network Configuration CLI

Command-line interface for managing the AI Network configuration.
Provides commands to view, enable, disable, and validate modules.
"""

import argparse
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.ConfigLoader import get_ai_network_config, reload_config
from abi import logger


def list_modules(args):
    """List all modules with their status"""
    config = get_ai_network_config()
    enabled_modules = config.get_enabled_modules()
    
    print("\n🤖 AI Network Module Status")
    print("=" * 50)
    
    for category, modules in enabled_modules.items():
        category_config = config.ai_network.get(category, {})
        category_enabled = category_config.get("enabled", False)
        
        print(f"\n📂 {category.upper().replace('_', ' ')} ({'✅ ENABLED' if category_enabled else '❌ DISABLED'})")
        print("-" * 30)
        
        if not category_enabled:
            print("   Category is disabled - no modules will load")
            continue
            
        if not modules:
            print("   No enabled modules in this category")
            continue
            
        for module in modules:
            name = module["name"]
            priority = module.get("priority", "N/A")
            description = module.get("description", "No description")
            print(f"   ✅ {name} (priority: {priority})")
            print(f"      {description}")
    
    # Show disabled modules if requested
    if args.show_disabled:
        print(f"\n❌ DISABLED MODULES")
        print("-" * 30)
        
        for category, category_config in config.ai_network.items():
            if category == "loading":
                continue
                
            modules = category_config.get("modules", [])
            disabled_modules = [m for m in modules if not m.get("enabled", False)]
            
            if disabled_modules:
                print(f"\n   {category}:")
                for module in disabled_modules:
                    name = module["name"]
                    description = module.get("description", "No description")
                    print(f"     ❌ {name} - {description}")


def enable_module(args):
    """Enable a specific module"""
    module_name = args.module
    category = args.category
    
    if not _update_module_status(module_name, category, True):
        sys.exit(1)
    
    print(f"✅ Enabled module '{module_name}' in category '{category}'")
    print("💡 Restart the application to apply changes")


def disable_module(args):
    """Disable a specific module"""
    module_name = args.module
    category = args.category
    
    if not _update_module_status(module_name, category, False):
        sys.exit(1)
    
    print(f"❌ Disabled module '{module_name}' in category '{category}'")
    print("💡 Restart the application to apply changes")


def validate_config(args):
    """Validate the AI Network configuration"""
    config = get_ai_network_config()
    issues = config.validate_configuration()
    
    if not issues:
        print("✅ AI Network configuration is valid")
        return
    
    print("❌ Configuration validation issues found:")
    for issue in issues:
        print(f"   - {issue}")
    
    sys.exit(1)


def show_config(args):
    """Show the current AI Network configuration"""
    config = get_ai_network_config()
    
    print("\n🔧 AI Network Configuration")
    print("=" * 50)
    
    # Pretty print the ai_network section
    ai_network_config = config.ai_network
    print(yaml.dump({"ai_network": ai_network_config}, default_flow_style=False, indent=2))


def reset_config(args):
    """Reset configuration to defaults"""
    if not args.confirm:
        print("⚠️ This will reset your AI Network configuration to defaults.")
        print("Use --confirm to proceed.")
        sys.exit(1)
    
    # Create a basic default configuration
    default_config = {
        "ai_network": {
            "core_models": {
                "enabled": True,
                "modules": [
                    {"name": "abi", "enabled": True, "priority": 1, "description": "Core ABI system"},
                    {"name": "chatgpt", "enabled": True, "priority": 2, "description": "OpenAI GPT models"},
                    {"name": "claude", "enabled": False, "priority": 3, "description": "Anthropic Claude models"}
                ]
            },
            "domain_experts": {
                "enabled": False,
                "modules": []
            },
            "applications": {
                "enabled": True,
                "modules": [
                    {"name": "github", "enabled": True, "priority": 1, "description": "GitHub integration"}
                ]
            },
            "custom_modules": {
                "enabled": True,
                "auto_discover": True,
                "modules": []
            },
            "loading": {
                "fail_on_error": True,
                "parallel_loading": False,
                "timeout_seconds": 30,
                "retry_attempts": 3
            }
        }
    }
    
    # Read existing config and update only ai_network section
    config_path = "config.yaml"
    try:
        with open(config_path, 'r') as file:
            existing_config = yaml.safe_load(file)
    except FileNotFoundError:
        existing_config = {}
    
    existing_config.update(default_config)
    
    # Write back to file
    with open(config_path, 'w') as file:
        yaml.dump(existing_config, file, default_flow_style=False, indent=2)
    
    print("✅ AI Network configuration reset to defaults")
    print("💡 Restart the application to apply changes")


def _update_module_status(module_name: str, category: str, enabled: bool) -> bool:
    """Update the enabled status of a module in the configuration file"""
    config_path = "config.yaml"
    
    try:
        # Read current configuration
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Navigate to the module
        ai_network = config.get("ai_network", {})
        category_config = ai_network.get(category, {})
        modules = category_config.get("modules", [])
        
        # Find and update the module
        module_found = False
        for module in modules:
            if module.get("name") == module_name:
                module["enabled"] = enabled
                module_found = True
                break
        
        if not module_found:
            print(f"❌ Module '{module_name}' not found in category '{category}'")
            print(f"💡 Available modules in {category}:")
            for module in modules:
                print(f"   - {module.get('name')}")
            return False
        
        # Write back to file
        with open(config_path, 'w') as file:
            yaml.dump(config, file, default_flow_style=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="AI Network Configuration Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                              # List all modules
  %(prog)s list --show-disabled              # List all modules including disabled ones
  %(prog)s enable chatgpt core_models        # Enable ChatGPT in core_models category
  %(prog)s disable gemini core_models        # Disable Gemini in core_models category
  %(prog)s validate                          # Validate configuration
  %(prog)s show                              # Show current configuration
  %(prog)s reset --confirm                   # Reset to default configuration
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all modules with their status')
    list_parser.add_argument('--show-disabled', action='store_true', 
                           help='Also show disabled modules')
    list_parser.set_defaults(func=list_modules)
    
    # Enable command
    enable_parser = subparsers.add_parser('enable', help='Enable a specific module')
    enable_parser.add_argument('module', help='Module name to enable')
    enable_parser.add_argument('category', help='Module category', 
                              choices=['core_models', 'domain_experts', 'applications', 'custom_modules'])
    enable_parser.set_defaults(func=enable_module)
    
    # Disable command
    disable_parser = subparsers.add_parser('disable', help='Disable a specific module')
    disable_parser.add_argument('module', help='Module name to disable')
    disable_parser.add_argument('category', help='Module category',
                               choices=['core_models', 'domain_experts', 'applications', 'custom_modules'])
    disable_parser.set_defaults(func=disable_module)
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate the configuration')
    validate_parser.set_defaults(func=validate_config)
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show current configuration')
    show_parser.set_defaults(func=show_config)
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset configuration to defaults')
    reset_parser.add_argument('--confirm', action='store_true', 
                            help='Confirm the reset operation')
    reset_parser.set_defaults(func=reset_config)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute the command
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
