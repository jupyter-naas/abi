#!/usr/bin/env python3
"""
Demo script for the Cyber Security CLI

Shows example interactions with the cyber security agent.
"""

import sys
from pathlib import Path

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

from apps.cli import CyberSecurityCLI  # noqa: E402

def demo_cli():
    """Demonstrate CLI functionality."""
    print("🎬 CYBER SECURITY CLI DEMO")
    print("=" * 40)
    
    cli = CyberSecurityCLI()
    
    # Demo commands
    demo_commands = [
        ("Dataset Overview", lambda: cli.show_overview()),
        ("Recent Events", lambda: cli.list_events()),
        ("Search Ransomware", lambda: cli.search_events(['ransomware'])),
        ("Analyze Event", lambda: cli.analyze_event(['cse-2025-001'])),
        ("Show Timeline", lambda: cli.show_timeline()),
        ("Sector Analysis", lambda: cli.show_sectors()),
    ]
    
    for title, command in demo_commands:
        print(f"\n🎯 {title}")
        print("-" * 30)
        try:
            command()
        except Exception as e:
            print(f"❌ Error in {title}: {e}")
        
        input("\n⏸️  Press Enter to continue...")
    
    print("\n🎉 Demo completed!")
    print("💡 To start the interactive CLI, run: python apps/cli.py")

if __name__ == "__main__":
    demo_cli()
