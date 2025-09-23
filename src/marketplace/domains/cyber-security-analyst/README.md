# Cyber Security Analyst Domain Module

Expert cyber security analyst specializing in threat analysis, vulnerability assessment, incident response, and security architecture.

## TL;DR

- Start the Cyber Security Analyst agent:
```bash
make chat-cyber-security-analyst-agent
```
- Or use the generic chat command:
```bash
make chat agent=CyberSecurityAnalystAgent
```

**Requirements**: Valid OpenAI API key (`OPENAI_API_KEY` environment variable)

## Overview

This domain module provides comprehensive cyber security analysis capabilities through specialized AI agents, ontologies, and workflows. It follows industry best practices and integrates with major security frameworks including NIST, MITRE ATT&CK, ISO 27001, and CIS Controls.

## Components

### Agent
- **CyberSecurityAnalystAgent**: Expert AI agent with deep cyber security knowledge
  - Threat intelligence and analysis
  - Vulnerability assessment and management
  - Incident response and forensics
  - Security architecture and controls
  - Risk management and compliance

### Ontologies
- **ThreatLandscape.ttl**: Comprehensive threat intelligence ontology
  - Threat actors (APT, cybercriminals, hacktivists, insider threats)
  - Attack vectors and techniques
  - MITRE ATT&CK framework integration
  - Threat campaigns and indicators of compromise

- **VulnerabilityManagement.ttl**: Vulnerability assessment and management ontology
  - Vulnerability types and classifications
  - Asset inventory and management
  - Risk assessment and CVSS scoring
  - Remediation planning and tracking

- **SecurityControls.ttl**: Security controls and compliance framework ontology
  - Technical, administrative, and physical controls
  - Preventive, detective, and corrective controls
  - Compliance frameworks (NIST, ISO 27001, CIS, SOC 2, PCI DSS)
  - Security architecture patterns

### Workflows
- **ThreatAssessmentWorkflow**: Comprehensive threat analysis and risk assessment
- **IncidentResponseWorkflow**: Structured incident response following NIST lifecycle
- **VulnerabilityAssessmentWorkflow**: End-to-end vulnerability management
- **SecurityArchitectureWorkflow**: Security architecture design and implementation

### Model Configuration
- **gpt_4o.py**: Optimized model configuration for security analysis tasks
  - Zero temperature for precision
  - Cyber security specific optimizations
  - Enhanced context handling for complex security scenarios

## Key Features

### Security Frameworks Integration
- **NIST Cybersecurity Framework**: Identify, Protect, Detect, Respond, Recover
- **MITRE ATT&CK**: Tactics, techniques, and procedures mapping
- **OWASP**: Web application security best practices
- **ISO 27001/27002**: Information security management standards
- **CIS Controls**: Critical security controls implementation
- **Zero Trust Architecture**: Never trust, always verify principles

### Capabilities
- **Threat Intelligence**: Advanced threat analysis and hunting
- **Vulnerability Management**: Systematic vulnerability assessment and remediation
- **Incident Response**: Structured incident handling and forensics
- **Security Architecture**: Defense-in-depth design and implementation
- **Risk Management**: Business-aligned security risk assessment
- **Compliance**: Multi-framework compliance assessment and reporting

### Use Cases
- Enterprise security assessments
- Incident response planning and execution
- Vulnerability management programs
- Security architecture reviews
- Compliance audits and gap analyses
- Threat hunting and intelligence analysis
- Security awareness and training

## Getting Started

🚧 **This module is currently a template and not functional yet.**

When implemented, you would:

1. Import the cyber security analyst agent
2. Configure the agent with your specific requirements
3. Use the specialized workflows for security tasks
4. Leverage the ontologies for knowledge management

## Security Considerations

This module handles sensitive security information and should be deployed with appropriate security controls:

- Secure configuration management
- Access control and authentication
- Audit logging and monitoring
- Data encryption and protection
- Secure communication channels

## Compliance

The module is designed to support compliance with major security standards and regulations:

- SOX (Sarbanes-Oxley Act)
- GDPR (General Data Protection Regulation)
- HIPAA (Health Insurance Portability and Accountability Act)
- PCI DSS (Payment Card Industry Data Security Standard)
- SOC 2 (Service Organization Control 2)
- FedRAMP (Federal Risk and Authorization Management Program)

## Contributing

When contributing to this module, please ensure:

- Security best practices are followed
- Industry standards are properly implemented
- Comprehensive testing is performed
- Documentation is updated accordingly
- Security reviews are conducted

## License

This module is part of the ABI framework and follows the same MIT license terms.
