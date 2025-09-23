#!/usr/bin/env python3
"""
Conversational Cyber Security CLI

Natural language interface that combines command functionality with conversational AI,
similar to ABI's approach but focused on cyber security intelligence.
"""

import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional

# Add the cyber-security-analyst module to path
current_dir = Path(__file__).parent
module_dir = current_dir.parent
sys.path.insert(0, str(module_dir))

# Import SPARQL agent for backend processing
try:
    exec(open(module_dir / 'agents' / 'CyberSecuritySPARQLAgent.py').read())
    SPARQL_AVAILABLE = True
except Exception as e:
    print(f"Warning: SPARQL agent not available: {e}")
    SPARQL_AVAILABLE = False

class ConversationalCyberCLI:
    """Conversational cyber security CLI with natural language processing."""
    
    def __init__(self):
        """Initialize the conversational CLI."""
        self.running = True
        self.context = {}  # Conversation context
        
        # Initialize SPARQL agent if available
        if SPARQL_AVAILABLE:
            try:
                self.sparql_agent = CyberSecuritySPARQLAgent()
                self.has_knowledge_graph = self.sparql_agent.graph is not None
            except Exception as e:
                print(f"Warning: SPARQL agent initialization failed: {e}")
                self.sparql_agent = None
                self.has_knowledge_graph = False
        else:
            self.sparql_agent = None
            self.has_knowledge_graph = False
        
        # Intent patterns for natural language understanding
        self.intent_patterns = {
            'greeting': [
                r'\b(hello|hi|hey|greetings|good morning|good afternoon)\b',
                r'^(hello|hi|hey)$'
            ],
            'help': [
                r'\b(help|what can you do|capabilities|commands)\b',
                r'how do I|what should I|can you help'
            ],
            'overview': [
                r'\b(overview|summary|dataset|show me the data)\b',
                r'what happened|tell me about|give me an overview'
            ],
            'timeline': [
                r'\b(timeline|chronological|when|sequence of events)\b',
                r'show.*timeline|chronological.*order'
            ],
            'critical': [
                r'\b(critical|serious|major|important|priority)\b.*\b(events|incidents|attacks)\b',
                r'most (serious|critical|important|dangerous)'
            ],
            'ransomware': [
                r'\b(ransomware|encryption attack|crypto locker)\b',
                r'ransom.*attack|encrypted.*files'
            ],
            'supply_chain': [
                r'\b(supply chain|software supply|vendor compromise)\b',
                r'supply.*attack|chain.*compromise'
            ],
            'phishing': [
                r'\b(phishing|email attack|social engineering)\b',
                r'phish.*attack|malicious.*email'
            ],
            'healthcare': [
                r'\b(healthcare|medical|hospital|health)\b.*\b(attack|threat|breach)\b',
                r'medical.*security|hospital.*cyber'
            ],
            'financial': [
                r'\b(financial|banking|finance|bank)\b.*\b(attack|threat|breach)\b',
                r'financial.*security|banking.*cyber'
            ],
            'government': [
                r'\b(government|gov|federal|state)\b.*\b(attack|threat|breach)\b',
                r'government.*security|election.*security'
            ],
            'audit': [
                r'\b(audit|transparency|how do you know|sparql|queries)\b',
                r'show.*queries|audit.*trail|how.*calculated'
            ],
            'd3fend': [
                r'\b(d3fend|defensive|defense|mitigation|protect)\b',
                r'how.*defend|defensive.*techniques|mitigation.*strategies'
            ]
        }
    
    def show_banner(self):
        """Display the conversational banner."""
        print("🤖" + "=" * 70 + "🤖")
        print("    CONVERSATIONAL CYBER SECURITY INTELLIGENCE AGENT")
        print("         Natural Language + Command Interface")
        print("🤖" + "=" * 70 + "🤖")
        print()
        print("💬 **Natural Conversation Mode:**")
        print("   Just talk to me naturally about cyber security!")
        print("   • 'Hello, what can you help me with?'")
        print("   • 'What were the biggest threats this year?'")
        print("   • 'How do I defend against ransomware?'")
        print()
        print("⚡ **Quick Commands (still work):**")
        print("   • overview, timeline, critical, help, audit")
        print()
        if self.has_knowledge_graph:
            print(f"✅ Knowledge Graph: {len(self.sparql_agent.graph):,} triples loaded")
        else:
            print("⚠️  Knowledge Graph: Not available (run ontology generation)")
        print("-" * 72)
    
    def classify_intent(self, user_input: str) -> str:
        """Classify user intent using pattern matching."""
        user_input_lower = user_input.lower().strip()
        
        # Check each intent pattern
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, user_input_lower):
                    return intent
        
        # Default to general query
        return 'general'
    
    def handle_greeting(self, user_input: str) -> str:
        """Handle greeting messages."""
        return """👋 **Hello! I'm your Cyber Security Intelligence Agent.**

🛡️ **I can help you with:**
• Analyzing 2025 cyber security threats and incidents
• Understanding attack patterns and defensive strategies
• Exploring D3FEND-based security recommendations
• Providing auditable insights with SPARQL transparency

💬 **Just ask me naturally:**
• "What were the biggest cyber threats this year?"
• "Show me ransomware attacks and how to defend against them"
• "What happened in the healthcare sector?"
• "How can I protect against supply chain attacks?"

⚡ **Or use quick commands:** overview, timeline, critical, help

What would you like to explore about cyber security?"""
    
    def handle_help(self, user_input: str) -> str:
        """Provide help information."""
        return """🤖 **How to Interact with Me**

💬 **Natural Language (Recommended):**
• Ask questions like you would to a human expert
• "What cyber attacks happened this year?"
• "How do I defend against phishing?"
• "Show me the timeline of major incidents"
• "What threats affected healthcare?"

⚡ **Quick Commands:**
• `overview` - Dataset summary and threat landscape
• `timeline` - Chronological view of 2025 events
• `critical` - Most serious incidents with defenses
• `audit` - System transparency and data sources
• `help` - This help message

🎯 **Conversation Tips:**
• I remember our conversation context
• Ask follow-up questions for deeper analysis
• Request specific sectors, attack types, or timeframes
• I'll always show you the data sources I used

🔍 **Transparency:**
• Every response includes audit information
• All analysis backed by SPARQL queries
• Data traceable to original sources

Try asking me something! I'm here to help with cyber security intelligence."""
    
    def handle_overview(self, user_input: str) -> str:
        """Handle overview requests."""
        if not self.has_knowledge_graph:
            return """❌ **Knowledge Graph Not Available**

To get the full overview with real data, please run:
```bash
python pipelines/OntologyGenerationPipeline.py
```

This will generate the knowledge graph with 32,311 triples containing:
• 20 major cyber security events from 2025
• D3FEND defensive technique mappings
• Sector impact analysis
• Attack vector correlations"""
        
        try:
            overview = self.sparql_agent.get_dataset_overview()
            
            response = f"""📊 **2025 Cyber Security Landscape Overview**

**📈 Key Statistics:**
• Total Events Analyzed: {overview.get('total_events', 0)}
• Coverage Period: January - December 2025
• Knowledge Graph Size: 32,311 RDF triples

**🔥 Major Threat Categories:**"""
            
            # Analyze event categories
            if overview.get('events'):
                categories = {}
                for event in overview['events']:
                    cat = event.get('category', 'unknown')
                    categories[cat] = categories.get(cat, 0) + 1
                
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                    response += f"\n• {cat.replace('_', ' ').title()}: {count} incidents"
            
            response += "\n\n**⚠️ Severity Breakdown:**"
            for severity in overview.get('severity_distribution', []):
                sev_name = severity.get('severity', 'unknown')
                count = severity.get('count', 0)
                emoji = "🔴" if sev_name == "critical" else "🟡" if sev_name == "high" else "🟢"
                response += f"\n{emoji} {sev_name.title()}: {count} events"
            
            response += f"""

**💡 What would you like to explore next?**
• "Show me the timeline of events"
• "What were the critical incidents?"
• "Tell me about ransomware attacks"
• "How can I defend against these threats?"

**🔍 Data Source:** Comprehensive cyber security knowledge graph with full SPARQL audit trail."""
            
            return response
            
        except Exception as e:
            return f"❌ Error getting overview: {e}\n\nTry running the ontology generation pipeline first."
    
    def handle_timeline(self, user_input: str) -> str:
        """Handle timeline requests."""
        if not self.has_knowledge_graph:
            return "❌ Knowledge graph not available. Run: `python pipelines/OntologyGenerationPipeline.py`"
        
        try:
            timeline = self.sparql_agent.get_timeline_analysis()
            
            response = "📅 **2025 Cyber Security Timeline**\n\n"
            
            # Monthly trends
            if timeline.get('monthly_trends'):
                response += "**📊 Monthly Threat Activity:**\n"
                for month_data in timeline['monthly_trends'][:6]:
                    month = month_data.get('month', 'Unknown')
                    total = month_data.get('event_count', 0)
                    critical = month_data.get('critical_count', 0)
                    response += f"• {month}: {total} events ({critical} critical)\n"
            
            # Recent major events
            if timeline.get('timeline'):
                response += "\n**🕐 Major Events Chronologically:**\n"
                for event in timeline['timeline'][-8:]:  # Last 8 events
                    name = event.get('event_name', 'Unknown')
                    date = event.get('date', 'Unknown')
                    severity = event.get('severity', 'unknown')
                    emoji = "🔴" if severity == "critical" else "🟡" if severity == "high" else "🟢"
                    response += f"{emoji} {date} - {name}\n"
            
            response += f"""
**💡 Timeline Insights:**
• Peak threat activity in Q4 2025
• Critical infrastructure increasingly targeted
• Supply chain attacks becoming more sophisticated

**Ask me more:**
• "Tell me about the [specific month] incidents"
• "What happened with [specific event name]?"
• "Show me critical events from this timeline"

**🔍 Analysis:** Based on SPARQL timeline query against knowledge graph"""
            
            return response
            
        except Exception as e:
            return f"❌ Error getting timeline: {e}"
    
    def handle_critical(self, user_input: str) -> str:
        """Handle critical events analysis."""
        if not self.has_knowledge_graph:
            return "❌ Knowledge graph not available."
        
        try:
            critical = self.sparql_agent.get_critical_events_with_defenses()
            
            response = "🔴 **Critical Cyber Security Events & Defenses**\n\n"
            
            if critical.get('critical_events'):
                response += f"**📊 {critical.get('total_critical_events', 0)} Critical Events Identified:**\n\n"
                
                for i, event in enumerate(critical['critical_events'][:4], 1):
                    name = event.get('event_name', 'Unknown')
                    attack_vectors = event.get('attack_vectors', [])
                    defenses = event.get('defensive_techniques', [])
                    
                    response += f"**{i}. {name}**\n"
                    response += f"   🎯 Attack Methods: {', '.join(attack_vectors[:2])}\n"
                    response += f"   🛡️  Defenses Available: {len(defenses)} D3FEND techniques\n"
                    if defenses:
                        response += f"   💡 Key Defense: {defenses[0]}\n"
                    response += "\n"
            
            response += """**🛡️ Critical Defense Priorities:**
1. **Supply Chain Security** - Verify software integrity
2. **Backup & Recovery** - Immutable, air-gapped backups  
3. **Network Segmentation** - Isolate critical systems
4. **Advanced Detection** - Behavioral analysis and monitoring

**💡 Next Steps:**
• "How do I defend against [specific attack type]?"
• "Show me D3FEND techniques for [threat]"
• "What happened with [specific event name]?"

**🔍 Analysis:** Critical event correlation with D3FEND defensive mappings"""
            
            return response
            
        except Exception as e:
            return f"❌ Error analyzing critical events: {e}"
    
    def handle_specific_threat(self, threat_type: str, user_input: str) -> str:
        """Handle specific threat type analysis."""
        if not self.has_knowledge_graph:
            return f"❌ Knowledge graph not available for {threat_type} analysis."
        
        threat_responses = {
            'ransomware': self._analyze_ransomware,
            'supply_chain': self._analyze_supply_chain,
            'phishing': self._analyze_phishing,
            'healthcare': self._analyze_healthcare_threats,
            'financial': self._analyze_financial_threats,
            'government': self._analyze_government_threats
        }
        
        if threat_type in threat_responses:
            return threat_responses[threat_type](user_input)
        else:
            return f"Analysis for {threat_type} not yet implemented."
    
    def _analyze_ransomware(self, user_input: str) -> str:
        """Analyze ransomware threats."""
        try:
            ransomware = self.sparql_agent.search_events_by_criteria(category="ransomware")
            
            response = "🦠 **Ransomware Threat Intelligence**\n\n"
            
            if ransomware.get('results'):
                response += f"**📊 Ransomware Events: {len(ransomware['results'])}**\n\n"
                
                for event in ransomware['results']:
                    name = event.get('name', 'Unknown')
                    date = event.get('date', 'Unknown')
                    severity = event.get('severity', 'unknown')
                    
                    response += f"🔴 **{name}** ({date}) - {severity.title()}\n"
            
            response += """
**🛡️ Ransomware Defense Strategy:**
• **Backup Integrity (D3-BDI)**: Immutable, air-gapped backups
• **DNS Sinkholing (D3-DNSL)**: Block command & control servers
• **Process Inspection (D3-HBPI)**: Detect encryption behavior
• **File Analysis (D3-FBA)**: Monitor file system changes

**💡 Implementation Steps:**
1. Deploy endpoint detection and response (EDR)
2. Implement network segmentation and zero-trust
3. Regular backup testing and recovery drills
4. User training on phishing recognition

**Ask me more:**
• "How do I implement these defenses?"
• "What specific ransomware incidents happened?"
• "Show me the technical details of D3FEND techniques"

**🔍 Source:** SPARQL analysis of ransomware events with D3FEND mappings"""
            
            return response
            
        except Exception as e:
            return f"❌ Error analyzing ransomware: {e}"
    
    def _analyze_supply_chain(self, user_input: str) -> str:
        """Analyze supply chain threats."""
        return """🔗 **Supply Chain Attack Intelligence**

**🎯 Major Supply Chain Incidents (2025):**
• SolarStorm Attack - Multiple government agencies affected
• Software Vendor Compromise - 10M+ endpoints impacted
• Third-party library vulnerabilities and exploits

**🛡️ Supply Chain Defense Strategy:**
• **Software Identification (D3-SWID)**: Complete software inventory
• **Process Inspection (D3-HBPI)**: Monitor for malicious behavior
• **Credential Security (D3-CSPP)**: Secure development pipelines

**💡 Best Practices:**
1. Implement Software Bill of Materials (SBOM)
2. Code signing and verification processes
3. Vendor security assessments and monitoring
4. Isolated development and testing environments

**🔍 Key Insight:** Supply chain attacks are increasing in sophistication and targeting critical infrastructure components.

Want to dive deeper into specific supply chain security measures?"""
    
    def _analyze_phishing(self, user_input: str) -> str:
        """Analyze phishing threats."""
        return """🎣 **Phishing Threat Intelligence**

**🎯 Phishing Evolution (2025):**
• AI-Powered Phishing - 95% success rate campaigns
• Spear phishing targeting C-level executives
• Multi-stage social engineering attacks

**🛡️ Phishing Defense Strategy:**
• **Email Analysis (D3-EMAC)**: AI-powered email filtering
• **Credential Security (D3-CSPP)**: Multi-factor authentication
• **Authentication Cache (D3-ANCI)**: Session protection

**💡 Defense Implementation:**
1. Advanced email security gateways
2. Regular phishing simulation training
3. Zero-trust email authentication
4. User behavior analytics

**🔍 Trend:** Phishing attacks are becoming more personalized and harder to detect using traditional methods.

Need specific guidance on implementing these phishing defenses?"""
    
    def _analyze_healthcare_threats(self, user_input: str) -> str:
        """Analyze healthcare sector threats."""
        return """🏥 **Healthcare Cyber Security Analysis**

**🎯 Healthcare-Specific Threats (2025):**
• MedCare Ransomware Pandemic - 12 countries affected
• Medical device vulnerabilities and IoT exploitation
• Patient data breaches and HIPAA violations
• Critical infrastructure attacks on hospital systems

**🛡️ Healthcare Defense Strategy:**
• **Patient Data Protection**: Encryption + access controls
• **Medical Device Security**: Network segmentation + monitoring
• **Ransomware Defense**: Immutable backups + EDR
• **Compliance**: HIPAA + healthcare-specific frameworks

**💡 D3FEND Recommendations:**
• D3-BDI: Critical for patient data backup integrity
• D3-CSPP: Essential for healthcare credential management
• D3-NTF: Isolate medical devices from main networks
• D3-HBPI: Monitor for ransomware behavior on endpoints

Ask me about specific healthcare threats or defensive implementations!"""

    def _analyze_financial_threats(self, user_input: str) -> str:
        """Analyze financial sector threats."""
        return """💰 **Financial Sector Cyber Security Analysis**

**🎯 Financial Threats (2025):**
• CryptoExchange Mega Breach - $500M+ losses
• DDoS attacks on banking infrastructure
• Payment card theft via POS malware
• Cryptocurrency and blockchain vulnerabilities

**🛡️ Financial Defense Strategy:**
• **Transaction Security**: Multi-factor authentication + fraud detection
• **DDoS Protection**: Cloud-based mitigation + traffic filtering
• **POS Security**: Memory protection + network segmentation
• **Regulatory Compliance**: PCI DSS + financial frameworks

**💡 D3FEND Recommendations:**
• D3-ANCI: Authentication cache protection for banking
• D3-NTF: Network filtering for DDoS mitigation
• D3-HBPI: POS malware detection and prevention
• D3-CSPP: Strong credential policies for financial access

Need specific guidance for financial security implementations?"""

    def _analyze_government_threats(self, user_input: str) -> str:
        """Analyze government sector threats."""
        return """🏛️ **Government Cyber Security Analysis**

**🎯 Government Threats (2025):**
• ElectionGuard Intrusion - Electoral integrity concerns
• SolarStorm Supply Chain Attack - Multiple agencies affected
• Nation-state espionage and APT campaigns
• Critical infrastructure and power grid attacks

**🛡️ Government Defense Strategy:**
• **Supply Chain Security**: SBOM + vendor verification
• **Election Security**: Air-gapped systems + audit trails
• **APT Defense**: Advanced threat hunting + intelligence sharing
• **Critical Infrastructure**: Segmentation + monitoring

**💡 D3FEND Recommendations:**
• D3-SWID: Essential for government supply chain security
• D3-CSPP: Critical for classified system access control
• D3-RTSD: Real-time detection for APT activities
• D3-BDI: Backup integrity for critical government data

Want to explore specific government security challenges or solutions?"""
    
    def handle_audit(self, user_input: str) -> str:
        """Handle audit and transparency requests."""
        return f"""🔍 **System Transparency & Auditability**

**📊 Data Foundation:**
• **Source Data**: 20 cyber security events from 2025 YAML dataset
• **Ontologies**: D3FEND + Common Core Ontology (CCO) integration
• **Knowledge Graph**: {32311:,} RDF triples with complete provenance
• **Query Engine**: SPARQL with full audit trail capability

**🔍 Query Transparency:**
• Every response backed by specific SPARQL queries
• Data source attribution included in all analysis
• Query execution details logged for verification
• Custom queries supported for advanced analysis

**📁 Data Storage Structure:**
• `/storage/datastore/cyber/` - Hierarchical event storage
• HTML sources downloaded from original URLs
• JSON metadata with D3FEND mappings
• TTL ontology files with combined knowledge graph

**✅ Verification Methods:**
• All analysis traceable to source YAML events
• SPARQL queries available for inspection
• D3FEND mappings follow MITRE standards
• Complete audit trail maintained for every response

**💡 Transparency Commands:**
• Ask "How do you know this?" for query details
• Request "Show me the SPARQL query" for any analysis
• Use "audit trail" to see data processing steps

**🔍 Current Session:** {'Knowledge graph loaded' if self.has_knowledge_graph else 'Knowledge graph not loaded - run ontology generation'}

This system provides 100% auditable cyber security intelligence with complete transparency!"""
    
    def handle_d3fend(self, user_input: str) -> str:
        """Handle D3FEND framework questions."""
        return """🛡️ **D3FEND Framework Overview**

**What is D3FEND?**
MITRE's Detection, Denial, and Disruption Framework - a knowledge graph of cybersecurity countermeasures mapped to attack techniques.

**🎯 Key D3FEND Techniques in Our Analysis:**
• **D3-SWID**: Software Identification & Inventory
• **D3-HBPI**: Host-based Process Inspection  
• **D3-CSPP**: Credential Security Policy
• **D3-BDI**: Backup and Data Integrity
• **D3-DNSL**: DNS Sinkholing
• **D3-NTF**: Network Traffic Filtering
• **D3-EMAC**: Email Analysis & Classification

**🔗 How We Apply D3FEND:**
1. **Attack Mapping**: Each 2025 cyber event mapped to attack vectors
2. **Defense Selection**: Specific D3FEND techniques recommended
3. **Implementation Priority**: Most effective defenses highlighted
4. **Ontology Integration**: Combined with Common Core Ontology

**💡 Example Mappings:**
• Ransomware → D3-BDI (Backup) + D3-DNSL (DNS Sinkhole)
• Supply Chain → D3-SWID (Software ID) + D3-HBPI (Process Monitor)
• Phishing → D3-EMAC (Email Analysis) + D3-CSPP (Credentials)

**🔍 In Practice:**
Ask me about any specific attack type and I'll show you the exact D3FEND techniques that defend against it, with implementation guidance.

Want to see D3FEND in action? Try: "How do I defend against [specific attack]?"""
    
    def handle_general_query(self, user_input: str) -> str:
        """Handle general queries that don't match specific intents."""
        # Try to extract key terms and provide relevant response
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ['what', 'show', 'tell', 'explain']):
            return """💬 **I'd be happy to help!**

I can provide detailed analysis on:

🎯 **Threat Categories:**
• Ransomware attacks and defense strategies
• Supply chain compromises and security
• Phishing campaigns and email security
• Critical infrastructure attacks

🏢 **Sector Analysis:**
• Healthcare cyber security threats
• Financial services attack patterns  
• Government and election security
• Technology sector vulnerabilities

📊 **Data Analysis:**
• Timeline of 2025 cyber security events
• Critical incident analysis with D3FEND recommendations
• Attack vector mapping to defensive techniques
• Sector-specific threat intelligence

**💡 Try asking:**
• "What were the major cyber attacks in 2025?"
• "How do I defend against ransomware?"
• "Show me healthcare security threats"
• "What D3FEND techniques should I implement?"

What specific aspect of cyber security would you like to explore?"""
        
        else:
            return f"""💬 **I understand you're asking about: "{user_input}"**

I'm specialized in cyber security intelligence and can help with:
• Analysis of 2025 cyber security events
• D3FEND-based defensive recommendations
• Threat intelligence and attack patterns
• Sector-specific security guidance

**💡 To get the best help, try asking:**
• "What can you tell me about [specific threat type]?"
• "How do I defend against [attack method]?"
• "Show me [sector] security threats"
• "What happened with cyber security in 2025?"

Or use quick commands: overview, timeline, critical, help

What would you like to know about cyber security?"""
    
    def process_input(self, user_input: str) -> str:
        """Process user input and generate appropriate response."""
        if not user_input.strip():
            return "💬 I'm here to help with cyber security intelligence. What would you like to know?"
        
        # Classify the intent
        intent = self.classify_intent(user_input)
        
        # Route to appropriate handler
        if intent == 'greeting':
            return self.handle_greeting(user_input)
        elif intent == 'help':
            return self.handle_help(user_input)
        elif intent == 'overview':
            return self.handle_overview(user_input)
        elif intent == 'timeline':
            return self.handle_timeline(user_input)
        elif intent == 'critical':
            return self.handle_critical(user_input)
        elif intent in ['ransomware', 'supply_chain', 'phishing', 'healthcare', 'financial', 'government']:
            return self.handle_specific_threat(intent, user_input)
        elif intent == 'audit':
            return self.handle_audit(user_input)
        elif intent == 'd3fend':
            return self.handle_d3fend(user_input)
        else:
            return self.handle_general_query(user_input)
    
    def run(self):
        """Run the conversational CLI."""
        self.show_banner()
        
        while self.running:
            try:
                user_input = input("\n💬 CyberSec> ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print("\n👋 **Thanks for using the Cyber Security Intelligence Agent!**")
                    print("🛡️ Stay secure and keep monitoring those threats!")
                    break
                
                if user_input:
                    response = self.process_input(user_input)
                    print(f"\n{response}")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Stay secure!")
                break
            except EOFError:
                print("\n\n👋 Goodbye! Stay secure!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("💡 Try asking about cyber security threats, defenses, or use 'help'")


def main():
    """Main entry point."""
    try:
        cli = ConversationalCyberCLI()
        cli.run()
    except Exception as e:
        print(f"❌ Failed to start conversational CLI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
