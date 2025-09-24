# Cyber Security Analyst Agent

A comprehensive AI agent for cyber security intelligence, threat analysis, and defensive recommendations using the D3FEND framework.

## 🎯 Overview

This agent provides **conversational AI** for cyber security analysis with full auditability through SPARQL queries. It combines natural language processing with command-based interaction, following the ABI IntentAgent pattern.

## 🚀 Quick Start

### Conversational Interface (Recommended)
```bash
# Start the conversational CLI
python apps/cli.py

# Example interactions:
💬 "Hello, what can you help me with?"
💬 "What were the biggest cyber threats in 2025?"
💬 "How do I defend against ransomware?"
💬 "Show me the timeline of events"
```

### Command Interface (Power Users)
```bash
# Quick commands still work:
💬 overview
💬 timeline  
💬 critical
💬 audit
```

### Demo
Use the conversational CLI above to explore capabilities interactively.

## 🛡️ Features

### Natural Language Understanding
- **Intent Classification**: Understands natural questions and commands
- **Context Awareness**: Maintains conversation flow and context
- **Flexible Input**: Supports both casual questions and technical queries

### Comprehensive Analysis
- **20 Major Cyber Events from 2025**: Complete incident database
- **D3FEND Integration**: MITRE defensive techniques mapping
- **Sector Analysis**: Healthcare, finance, government threat intelligence
- **Attack Vector Mapping**: Specific defensive recommendations

### Full Auditability
- **SPARQL Transparency**: Every response shows underlying queries
- **Data Provenance**: Complete traceability to source data
- **Knowledge Graph**: 32,311 RDF triples with ontology integration
- **Audit Trails**: Full transparency for all analysis

## 📊 Data Sources

### Events Dataset
- **Source**: `events.yaml` - 20 major cyber security events from 2025
- **Coverage**: Supply chain attacks, ransomware, data breaches, critical infrastructure
- **Metadata**: Attack vectors, sectors affected, severity levels

### Knowledge Graph
- **D3FEND Ontology**: Complete MITRE defensive framework
- **CCO Integration**: Common Core Ontology mappings
- **Event Instances**: Real incident data mapped to ontological concepts
- **SPARQL Queries**: 6 predefined + unlimited custom queries

### Storage Structure
```
/storage/datastore/cyber/
├── 2025/
│   ├── 01/supply_chain_attack/cse-2025-001/
│   │   ├── source_1_demo.html
│   │   ├── event_metadata.json
│   │   └── d3fend_mapping.json
│   └── [other events...]
└── cyber_security_ontology.ttl
```

## 🤖 Agent Capabilities

### Conversational Modes

#### Natural Language Examples
```
💬 "What happened with cyber security this year?"
🤖 Provides comprehensive 2025 threat landscape overview

💬 "Tell me about ransomware attacks"  
🤖 Shows ransomware incidents with D3FEND defensive techniques

💬 "How do I protect against supply chain attacks?"
🤖 Detailed D3FEND implementation guidance with audit trail

💬 "What threats affected healthcare?"
🤖 Sector-specific analysis with defensive priorities
```

#### Command Examples
```
💬 overview
🤖 Dataset statistics and threat category breakdown

💬 timeline
🤖 Chronological analysis of 2025 cyber events

💬 critical
🤖 Critical incidents with defensive recommendations

💬 audit
🤖 Complete system transparency and data sources
```

### Intent Classification
The agent automatically classifies user input into intents:
- **Greeting**: Hello, hi, what can you help with
- **Analysis**: Overview, timeline, critical events
- **Threats**: Ransomware, supply chain, phishing
- **Sectors**: Healthcare, financial, government
- **Defense**: D3FEND techniques, recommendations
- **Audit**: Transparency, SPARQL queries

## 🔍 Technical Architecture

### ABI Integration
- **IntentAgent Framework**: Natural language processing with intent mapping
- **System Prompts**: Conversational AI with cyber security expertise
- **Agent Configuration**: Seamless integration with ABI ecosystem

### SPARQL Backend
- **Knowledge Graph**: RDF triples with complete cyber security ontology
- **Query Engine**: Real-time SPARQL execution for all analysis
- **Audit Trails**: Every response includes query transparency

### Natural Language Processing
- **Pattern Matching**: Regex-based intent classification
- **Context Preservation**: Conversation state management
- **Flexible Responses**: Adaptive to user input style

## 📈 Usage Patterns

### For Security Analysts
```bash
# Start with overview
💬 "Give me an overview of 2025 cyber threats"

# Dive into specific threats
💬 "Tell me more about the critical incidents"

# Get defensive guidance
💬 "How do I defend against these attacks?"

# Verify with audit trails
💬 "Show me how you calculated this"
```

### For Decision Makers
```bash
# Strategic overview
💬 "What are the biggest cyber risks we face?"

# Sector-specific intelligence
💬 "What threats are affecting our industry?"

# Implementation priorities
💬 "What defensive measures should we prioritize?"
```

### For Researchers
```bash
# Data exploration
💬 audit

# Custom analysis
💬 "Show me supply chain attack patterns"

# Methodology verification
💬 "What SPARQL queries are available?"
```

## 🛠️ Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Generate knowledge graph (first time)
python pipelines/OntologyGenerationPipeline.py

# Test the agent
python apps/demo_conversational.py
```

### Architecture Components
- **ConversationalCyberAgent.py**: ABI IntentAgent integration
- **cli.py**: Standalone natural language interface
- **CyberSecuritySPARQLAgent.py**: SPARQL query engine
- **OntologyGenerationPipeline.py**: Knowledge graph generation

### Extending the Agent
1. **Add New Intents**: Update intent patterns in `cli.py`
2. **Custom Analysis**: Add methods for new threat categories
3. **SPARQL Queries**: Extend query library in SPARQL agent
4. **Data Sources**: Add new events to `events.yaml`

## 🔒 Security & Compliance

### Data Integrity
- **Immutable Sources**: Original HTML and metadata preserved
- **Audit Trails**: Complete query execution logging
- **Provenance**: Traceable from analysis back to source events

### Transparency
- **Open Queries**: All SPARQL queries available for inspection
- **Methodology**: Clear analytical framework using D3FEND standards
- **Verification**: Independent validation of all analysis possible

## 🎉 Key Achievements

✅ **Conversational AI**: Natural language cyber security intelligence  
✅ **Full Auditability**: 100% transparent analysis with SPARQL queries  
✅ **D3FEND Integration**: Complete defensive technique mapping  
✅ **ABI Compatibility**: Seamless integration with IntentAgent framework  
✅ **Hybrid Interface**: Both natural language and command support  
✅ **Real Data**: 20 actual cyber security events from 2025  
✅ **Knowledge Graph**: 32,311 RDF triples with ontological rigor  

## 🚀 Next Steps

The agent is ready for:
- **Production Deployment**: Full ABI integration with OpenAI API
- **Data Expansion**: Additional cyber security events and sources
- **Advanced Analytics**: Machine learning integration for predictive analysis
- **Custom Ontologies**: Domain-specific security frameworks

---

**Start chatting with your cyber security intelligence agent:**
```bash
python apps/cli.py
```
