#!/usr/bin/env python3
"""
Cyber Security Analyst CLI Chat Interface

A simple command-line interface for chatting with the cyber security agent
about the 2025 cyber security events dataset.
"""

import sys
import json
from pathlib import Path

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

try:
    from workflows.CyberEventAnalysisWorkflow import CyberEventAnalysisWorkflow, analyze_cyber_events, get_defensive_recommendations
except ImportError as e:
    print(f"❌ Error importing workflow: {e}")
    print("Make sure you're running from the cyber-security-analyst directory")
    sys.exit(1)

class CyberSecurityCLI:
    """Simple CLI interface for cyber security agent interaction."""
    
    def __init__(self):
        """Initialize the CLI interface."""
        self.workflow = CyberEventAnalysisWorkflow()
        self.commands = {
            'help': self.show_help,
            'overview': self.show_overview,
            'events': self.list_events,
            'search': self.search_events,
            'analyze': self.analyze_event,
            'timeline': self.show_timeline,
            'sectors': self.show_sectors,
            'quit': self.quit_app,
            'exit': self.quit_app
        }
        self.running = True
    
    def show_banner(self):
        """Display the application banner."""
        print("🔒" + "=" * 60 + "🔒")
        print("    CYBER SECURITY ANALYST - AI CHAT INTERFACE")
        print("         2025 Cyber Events Intelligence System")
        print("🔒" + "=" * 60 + "🔒")
        print()
        print("💬 Chat with the AI about cyber security events from 2025")
        print("🛡️  Get D3FEND-based defensive recommendations")
        print("📊 Analyze threats by sector, timeline, or severity")
        print()
        print("Type 'help' for available commands or just ask questions naturally!")
        print("Type 'quit' or 'exit' to leave")
        print("-" * 62)
    
    def show_help(self, args=None):
        """Show available commands."""
        print("\n🤖 CYBER SECURITY AI ASSISTANT - COMMANDS")
        print("=" * 50)
        print("📋 BASIC COMMANDS:")
        print("  help                    - Show this help message")
        print("  overview               - Dataset overview and statistics")
        print("  events                 - List recent events")
        print("  timeline               - Show chronological timeline")
        print("  sectors                - Show affected sectors")
        print("  quit/exit              - Exit the application")
        print()
        print("🔍 ANALYSIS COMMANDS:")
        print("  search <query>         - Search events (e.g., 'search ransomware')")
        print("  analyze <event_id>     - Get D3FEND analysis for specific event")
        print()
        print("💬 NATURAL LANGUAGE QUERIES:")
        print("  'Show me ransomware attacks'")
        print("  'What happened in healthcare?'")
        print("  'Tell me about critical events'")
        print("  'Analyze supply chain attacks'")
        print("  'What are the latest threats?'")
        print()
        print("🛡️  D3FEND ANALYSIS:")
        print("  'Get recommendations for cse-2025-001'")
        print("  'How to defend against ransomware?'")
        print("  'Show defensive measures'")
        print("-" * 50)
    
    def show_overview(self, args=None):
        """Show dataset overview."""
        print("\n📊 CYBER SECURITY DATASET OVERVIEW")
        print("=" * 40)
        
        try:
            overview = self.workflow.get_dataset_overview()
            
            if 'error' in overview:
                print(f"❌ {overview['error']}")
                return
            
            stats = overview.get('statistics', {})
            print(f"📈 Total Events: {stats.get('total_events', 0)}")
            print(f"📂 Categories: {stats.get('categories', 0)}")
            print(f"🏢 Affected Sectors: {stats.get('affected_sectors', 0)}")
            print(f"⚔️  Attack Vectors: {stats.get('attack_vectors', 0)}")
            print(f"🛡️  D3FEND Techniques: {stats.get('d3fend_techniques', 0)}")
            
            print("\n🔥 TOP THREAT CATEGORIES:")
            for category, count in list(overview.get('top_categories', {}).items())[:5]:
                print(f"  • {category.replace('_', ' ').title()}: {count} events")
            
            print("\n🎯 MOST TARGETED SECTORS:")
            for sector, count in list(overview.get('top_sectors', {}).items())[:5]:
                print(f"  • {sector.replace('_', ' ').title()}: {count} events")
            
            print("\n⚠️  SEVERITY DISTRIBUTION:")
            for severity, count in overview.get('severity_distribution', {}).items():
                emoji = "🔴" if severity == "critical" else "🟡" if severity == "high" else "🟢"
                print(f"  {emoji} {severity.title()}: {count} events")
                
        except Exception as e:
            print(f"❌ Error getting overview: {e}")
    
    def list_events(self, args=None):
        """List recent events."""
        print("\n📋 RECENT CYBER SECURITY EVENTS")
        print("=" * 40)
        
        try:
            timeline = self.workflow.get_threat_timeline()
            
            if not timeline:
                print("❌ No events found")
                return
            
            # Show last 10 events
            recent_events = timeline[-10:]
            
            for event in recent_events:
                date = event.get('date', 'Unknown')
                name = event.get('name', 'Unknown Event')
                severity = event.get('severity', 'unknown')
                category = event.get('category', 'unknown')
                event_id = event.get('event_id', '')
                
                # Severity emoji
                severity_emoji = {
                    'critical': '🔴',
                    'high': '🟡', 
                    'medium': '🟠',
                    'low': '🟢'
                }.get(severity, '⚪')
                
                print(f"{severity_emoji} {date} | {name}")
                print(f"   📂 {category.replace('_', ' ').title()} | ID: {event_id}")
                print()
                
        except Exception as e:
            print(f"❌ Error listing events: {e}")
    
    def search_events(self, args):
        """Search events by query."""
        if not args:
            print("❌ Please provide a search query. Example: search ransomware")
            return
        
        query = ' '.join(args)
        print(f"\n🔍 SEARCHING FOR: '{query}'")
        print("=" * 40)
        
        try:
            # Use the natural language query interface
            result = analyze_cyber_events(query)
            
            if isinstance(result, dict):
                # Handle different result types
                if 'ransomware_events' in result:
                    events = result['ransomware_events']
                    print(f"🦠 Found {len(events)} ransomware events:")
                elif 'phishing_events' in result:
                    events = result['phishing_events']
                    print(f"🎣 Found {len(events)} phishing events:")
                elif 'critical_events' in result:
                    events = result['critical_events']
                    print(f"🔴 Found {len(events)} critical events:")
                elif 'message' in result:
                    print(f"💬 {result['message']}")
                    return
                else:
                    print(f"📄 Search results: {json.dumps(result, indent=2)}")
                    return
                
                # Display events
                for event in events[:5]:  # Show first 5 results
                    name = event.get('name', 'Unknown')
                    date = event.get('date', 'Unknown')
                    severity = event.get('severity', 'unknown')
                    event_id = event.get('id', '')
                    
                    severity_emoji = {
                        'critical': '🔴',
                        'high': '🟡',
                        'medium': '🟠', 
                        'low': '🟢'
                    }.get(severity, '⚪')
                    
                    print(f"{severity_emoji} {name}")
                    print(f"   📅 {date} | ID: {event_id}")
                    print(f"   📝 {event.get('description', '')[:100]}...")
                    print()
            
        except Exception as e:
            print(f"❌ Error searching: {e}")
    
    def analyze_event(self, args):
        """Analyze specific event with D3FEND recommendations."""
        if not args:
            print("❌ Please provide an event ID. Example: analyze cse-2025-001")
            return
        
        event_id = args[0]
        print(f"\n🛡️  D3FEND ANALYSIS FOR: {event_id}")
        print("=" * 50)
        
        try:
            analysis = get_defensive_recommendations(event_id)
            
            if 'error' in analysis:
                print(f"❌ {analysis['error']}")
                return
            
            # Show attack summary
            attack_summary = analysis.get('attack_summary', {})
            print("⚔️  ATTACK VECTORS:")
            for vector in attack_summary.get('attack_vectors', []):
                print(f"   • {vector.replace('_', ' ').title()}")
            
            # Show defensive techniques
            techniques = analysis.get('defensive_techniques', [])
            print(f"\n🛡️  DEFENSIVE TECHNIQUES ({len(techniques)}):")
            for technique in techniques:
                print(f"   • {technique.get('technique_id')}: {technique.get('name')}")
                print(f"     📝 {technique.get('description')}")
                print(f"     📂 Category: {technique.get('category')}")
                print()
            
            # Show implementation priority
            priority = analysis.get('implementation_priority', [])
            if priority:
                print("🎯 IMPLEMENTATION PRIORITY:")
                for i, tech_id in enumerate(priority[:3], 1):
                    print(f"   {i}. {tech_id}")
            
            # Show recommendations
            recommendations = analysis.get('recommendations', [])
            if recommendations:
                print(f"\n💡 DEFENSIVE RECOMMENDATIONS ({len(recommendations)}):")
                for i, rec in enumerate(recommendations[:3], 1):
                    priority_emoji = "🔴" if rec.get('priority') == 'Critical' else "🟡" if rec.get('priority') == 'High' else "🟠"
                    print(f"   {i}. {priority_emoji} [{rec.get('priority')}] {rec.get('action')}")
                    print(f"      📝 {rec.get('description')}")
                    print()
            
        except Exception as e:
            print(f"❌ Error analyzing event: {e}")
    
    def show_timeline(self, args=None):
        """Show chronological timeline."""
        print("\n📅 CYBER SECURITY TIMELINE 2025")
        print("=" * 40)
        
        try:
            timeline = self.workflow.get_threat_timeline()
            
            if not timeline:
                print("❌ No timeline data available")
                return
            
            current_month = None
            for event in timeline:
                date = event.get('date', '')
                if date:
                    month = date[:7]  # YYYY-MM
                    if month != current_month:
                        current_month = month
                        print(f"\n📆 {month}")
                        print("-" * 20)
                
                name = event.get('name', 'Unknown')
                severity = event.get('severity', 'unknown')
                category = event.get('category', 'unknown')
                
                severity_emoji = {
                    'critical': '🔴',
                    'high': '🟡',
                    'medium': '🟠',
                    'low': '🟢'
                }.get(severity, '⚪')
                
                print(f"{severity_emoji} {date} - {name}")
                print(f"   📂 {category.replace('_', ' ').title()}")
                
        except Exception as e:
            print(f"❌ Error showing timeline: {e}")
    
    def show_sectors(self, args=None):
        """Show affected sectors analysis."""
        print("\n🏢 SECTOR THREAT ANALYSIS")
        print("=" * 30)
        
        try:
            overview = self.workflow.get_dataset_overview()
            sectors = overview.get('top_sectors', {})
            
            print("🎯 MOST TARGETED SECTORS:")
            for sector, count in list(sectors.items())[:10]:
                sector_name = sector.replace('_', ' ').title()
                bar = "█" * min(count, 20)  # Simple bar chart
                print(f"  {sector_name:<25} {bar} ({count})")
            
            print("\n💡 TIP: Use 'search healthcare' or 'search financial' to analyze specific sectors")
            
        except Exception as e:
            print(f"❌ Error showing sectors: {e}")
    
    def process_natural_language(self, user_input):
        """Process natural language queries."""
        print("\n🤖 AI RESPONSE:")
        print("-" * 20)
        
        try:
            result = analyze_cyber_events(user_input)
            
            if isinstance(result, dict):
                if 'dataset_info' in result:
                    # Overview response
                    stats = result.get('statistics', {})
                    print(f"📊 I found {stats.get('total_events', 0)} cyber security events from 2025.")
                    print(f"The dataset covers {stats.get('categories', 0)} different attack categories")
                    print(f"affecting {stats.get('affected_sectors', 0)} sectors worldwide.")
                    
                elif 'timeline' in result:
                    timeline = result['timeline']
                    print(f"📅 Here's the timeline of {len(timeline)} cyber security events:")
                    for event in timeline[-5:]:  # Show last 5
                        print(f"  • {event.get('date')} - {event.get('name')}")
                        
                elif any(key.endswith('_events') for key in result.keys()):
                    # Events response
                    for key, events in result.items():
                        if key.endswith('_events') and isinstance(events, list):
                            event_type = key.replace('_events', '').replace('_', ' ').title()
                            print(f"🔍 I found {len(events)} {event_type} events:")
                            for event in events[:3]:  # Show first 3
                                print(f"  • {event.get('name')} ({event.get('date')})")
                                print(f"    Severity: {event.get('severity', 'unknown').title()}")
                            if len(events) > 3:
                                print(f"  ... and {len(events) - 3} more events")
                            break
                
                elif 'message' in result:
                    print(f"💬 {result['message']}")
                    
                else:
                    # Generic response
                    print("📄 Here's what I found:")
                    print(json.dumps(result, indent=2))
            
        except Exception as e:
            print(f"❌ Sorry, I encountered an error: {e}")
    
    def quit_app(self, args=None):
        """Quit the application."""
        print("\n👋 Thanks for using the Cyber Security AI Assistant!")
        print("🛡️  Stay secure and keep monitoring those threats!")
        self.running = False
    
    def run(self):
        """Run the CLI interface."""
        self.show_banner()
        
        while self.running:
            try:
                # Get user input
                user_input = input("\n🔒 CyberSec AI> ").strip()
                
                if not user_input:
                    continue
                
                # Parse command
                parts = user_input.split()
                command = parts[0].lower()
                args = parts[1:] if len(parts) > 1 else []
                
                # Handle commands
                if command in self.commands:
                    self.commands[command](args)
                else:
                    # Treat as natural language query
                    self.process_natural_language(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except EOFError:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("Type 'help' for available commands")


def main():
    """Main entry point."""
    try:
        cli = CyberSecurityCLI()
        cli.run()
    except Exception as e:
        print(f"❌ Failed to start CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
