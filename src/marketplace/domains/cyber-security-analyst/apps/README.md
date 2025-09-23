# Cyber Security Analyst Apps

Interactive applications for the Cyber Security Analyst domain.

## 🔒 CLI Chat Interface

A simple command-line interface for chatting with the cyber security AI agent.

### Quick Start

```bash
# Navigate to the cyber-security-analyst directory
cd src/marketplace/domains/cyber-security-analyst

# Run the interactive CLI
python apps/cli.py

# Or run the demo
python apps/demo.py
```

### Features

- **Natural Language Queries**: Ask questions in plain English
- **Event Analysis**: Get detailed information about specific cyber events
- **D3FEND Integration**: Receive defensive recommendations based on MITRE D3FEND
- **Timeline Analysis**: Explore events chronologically
- **Sector Analysis**: Analyze threats by industry sector

### Example Commands

```bash
# Basic commands
help                    # Show available commands
overview               # Dataset statistics
events                 # List recent events
timeline               # Chronological view
sectors                # Sector analysis

# Search and analysis
search ransomware      # Find ransomware events
analyze cse-2025-001   # Get D3FEND analysis for specific event

# Natural language queries
"Show me critical events"
"What happened in healthcare?"
"Tell me about supply chain attacks"
"Get recommendations for ransomware defense"
```

### Sample Interaction

```
🔒 CyberSec AI> overview
📊 CYBER SECURITY DATASET OVERVIEW
========================================
📈 Total Events: 20
📂 Categories: 19
🏢 Affected Sectors: 44
⚔️  Attack Vectors: 54
🛡️  D3FEND Techniques: 12

🔥 TOP THREAT CATEGORIES:
  • Supply Chain Attack: 2 events
  • Ransomware: 1 events
  • Data Breach: 1 events

🔒 CyberSec AI> search ransomware
🔍 SEARCHING FOR: 'ransomware'
========================================
🦠 Found 1 ransomware events:
🔴 MedCare Ransomware Pandemic
   📅 2025-03-05 | ID: cse-2025-003
   📝 Coordinated ransomware attack on healthcare providers across 12 countries...

🔒 CyberSec AI> analyze cse-2025-003
🛡️  D3FEND ANALYSIS FOR: cse-2025-003
==================================================
⚔️  ATTACK VECTORS:
   • Phishing
   • Lateral Movement
   • Encryption

🛡️  DEFENSIVE TECHNIQUES (3):
   • D3-BDI: Backup and Data Integrity
     📝 Maintain secure backups and verify data integrity
     📂 Category: Data Backup
   
   • D3-DNSL: DNS Sinkholing
     📝 Redirect malicious DNS queries to controlled servers
     📂 Category: Network Isolation

💡 DEFENSIVE RECOMMENDATIONS (2):
   1. 🔴 [Critical] Implement immutable backup strategy
      📝 Deploy air-gapped, immutable backups with regular recovery testing
   
   2. 🟡 [High] Deploy endpoint detection and response (EDR)
      📝 Monitor endpoint behavior for ransomware indicators
```

## Files

- `cli.py` - Main interactive CLI application
- `demo.py` - Demonstration script showing CLI features
- `README.md` - This documentation

## Requirements

The CLI uses the cyber security analysis workflow and requires:
- Python 3.7+
- Access to the cyber security events dataset
- The CyberEventAnalysisWorkflow module

## Usage Tips

1. **Start with `overview`** to understand the dataset
2. **Use `help`** to see all available commands
3. **Try natural language** - the AI understands conversational queries
4. **Explore specific events** with the `analyze` command for D3FEND recommendations
5. **Use `search`** to find events by category, sector, or attack type
