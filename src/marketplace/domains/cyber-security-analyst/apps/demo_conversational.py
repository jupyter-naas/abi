#!/usr/bin/env python3
"""
Demo: Conversational Cyber Security Agent

Demonstrates both natural language conversation and command-based interaction
with the cyber security intelligence system.
"""

import sys
from pathlib import Path

# Add the cyber-security-analyst module to path  # noqa: E402
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

from apps.cli import ConversationalCyberCLI


def demo_conversation():
    """Demonstrate conversational capabilities."""
    print("🎭" + "=" * 70 + "🎭")
    print("    DEMO: CONVERSATIONAL CYBER SECURITY AGENT")
    print("🎭" + "=" * 70 + "🎭")
    print()
    
    # Create CLI instance
    cli = ConversationalCyberCLI()
    
    # Demo conversation scenarios
    demo_inputs = [
        ("👋 Greeting", "Hello, what can you help me with?"),
        ("📊 Natural Overview", "What were the biggest cyber threats this year?"),
        ("🦠 Threat Inquiry", "Tell me about ransomware attacks"),
        ("🛡️ Defense Question", "How do I defend against supply chain attacks?"),
        ("⚡ Quick Command", "timeline"),
        ("🔍 Audit Request", "How do you know this information?"),
        ("💡 Help Request", "What else can you help me with?")
    ]
    
    for scenario, user_input in demo_inputs:
        print(f"\n{scenario}")
        print("-" * 50)
        print(f"💬 User: {user_input}")
        print()
        
        # Get response
        response = cli.process_input(user_input)
        
        # Show truncated response for demo
        lines = response.split('\n')
        if len(lines) > 15:
            truncated_response = '\n'.join(lines[:15]) + f"\n... [+{len(lines)-15} more lines]"
        else:
            truncated_response = response
            
        print(f"🤖 CyberSec: {truncated_response}")
        print()
    
    print("🎉" + "=" * 70 + "🎉")
    print("    DEMO COMPLETE - CONVERSATIONAL AGENT READY!")
    print("🎉" + "=" * 70 + "🎉")
    print()
    print("💡 **Key Features Demonstrated:**")
    print("   ✅ Natural language understanding")
    print("   ✅ Command recognition (overview, timeline, etc.)")
    print("   ✅ Context-aware responses")
    print("   ✅ SPARQL-backed analysis with audit trails")
    print("   ✅ D3FEND defensive recommendations")
    print()
    print("🚀 **To start chatting:** python apps/conversational_cli.py")
    print("🔗 **ABI Integration:** Uses IntentAgent pattern for natural conversation")


if __name__ == "__main__":
    demo_conversation()
