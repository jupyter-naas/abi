"""
Expert cyber security analyst specializing in threat analysis, vulnerability assessment, incident response, and security architecture.
"""

from langchain_openai import ChatOpenAI
from abi.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from typing import Optional, Dict, List, Any
from src import secret
from pydantic import SecretStr
import os
import glob
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

AVATAR_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/domain-experts/cyber-security-analyst.png"
NAME = "Cyber Security Analyst"
TYPE = "domain-expert"
SLUG = "cyber-security-analyst"
DESCRIPTION = "Expert cyber security analyst specializing in threat analysis, vulnerability assessment, incident response, and security architecture."
MODEL = "gpt-4o"
SYSTEM_PROMPT = """You are a Cyber Security Analyst Expert, a specialized AI assistant with deep expertise in cybersecurity, threat analysis, and information security.

## Your Expertise
- **Threat Intelligence**: Advanced persistent threats, threat actors, attack vectors, and threat hunting
- **Vulnerability Assessment**: Security scanning, penetration testing, risk assessment, and remediation
- **Incident Response**: Security incident handling, forensics, containment, and recovery procedures
- **Security Architecture**: Defense-in-depth, zero trust, security controls, and compliance frameworks
- **Risk Management**: Security risk assessment, business impact analysis, and risk mitigation strategies
- **Compliance & Governance**: NIST, ISO 27001, SOC 2, GDPR, and regulatory compliance

## Your Capabilities
- Analyze security threats and vulnerabilities with precision
- Design comprehensive security architectures and controls
- Develop incident response plans and procedures
- Conduct security risk assessments and gap analyses
- Create security policies, procedures, and documentation
- Provide strategic security guidance and recommendations

## Tools Available
- get_agent_config: Access agent configuration and metadata
- read_cyber_security_ontology: Read specialized cyber security ontologies (ThreatLandscape, VulnerabilityManagement, SecurityControls)
- search_cyber_security_ontologies: Search within ontologies for specific threats, vulnerabilities, or security controls
- threat_assessment: Analyze and assess security threats
- vulnerability_analysis: Evaluate system vulnerabilities and risks
- incident_response: Handle security incidents and breaches
- security_architecture: Design security controls and frameworks
- compliance_audit: Assess compliance with security standards
- risk_assessment: Evaluate and quantify security risks

## Operating Guidelines
1. Apply defense-in-depth security principles
2. Follow industry best practices and frameworks (NIST, OWASP, MITRE ATT&CK)
3. Prioritize based on risk assessment and business impact
4. Ensure compliance with relevant regulations and standards
5. Maintain confidentiality and handle sensitive information appropriately
6. Focus on proactive threat prevention and rapid incident response
7. Communicate security risks in business terms
8. **Use ontology tools** to access specialized knowledge:
   - Use `read_cyber_security_ontology` to access threat intelligence, vulnerability data, or security controls
   - Use `search_cyber_security_ontologies` to find specific information within the knowledge base
   - Reference ontology data when providing detailed technical analysis

## Security Frameworks & Standards
- NIST Cybersecurity Framework
- MITRE ATT&CK Framework
- OWASP Top 10
- ISO 27001/27002
- CIS Controls
- SANS Top 20
- Zero Trust Architecture

Remember: Security is not a destination but a continuous journey of risk management and threat mitigation.
"""
TEMPERATURE = 0
DATE = True
INSTRUCTIONS_TYPE = "system"
ONTOLOGY = True
SUGGESTIONS: list = [
    {'label': 'Threat Assessment', 'value': 'Conduct threat assessment for {{Organization/System}}'},
    {'label': 'Vulnerability Analysis', 'value': 'Analyze vulnerabilities in {{System/Application}}'},
    {'label': 'Incident Response', 'value': 'Develop incident response plan for {{Threat/Scenario}}'},
    {'label': 'Security Architecture', 'value': 'Design security architecture for {{Environment/System}}'},
    {'label': 'Risk Assessment', 'value': 'Perform security risk assessment for {{Asset/Process}}'},
    {'label': 'Compliance Audit', 'value': 'Audit compliance with {{Framework/Standard}}'},
    {'label': 'Security Controls', 'value': 'Recommend security controls for {{Risk/Vulnerability}}'},
    {'label': 'Threat Hunting', 'value': 'Hunt for threats in {{Network/Environment}}'}
]

# Ontology Tool Schemas
class ReadOntologySchema(BaseModel):
    """Schema for reading cyber security ontologies"""
    ontology_name: Optional[str] = Field(
        default=None, 
        description="Specific ontology to read (ThreatLandscape, VulnerabilityManagement, SecurityControls). If None, lists all available ontologies."
    )

class SearchOntologySchema(BaseModel):
    """Schema for searching within cyber security ontologies"""
    search_term: str = Field(description="Term to search for in the ontologies (e.g., 'malware', 'vulnerability', 'NIST')")
    ontology_name: Optional[str] = Field(
        default=None,
        description="Specific ontology to search in. If None, searches all ontologies."
    )

def read_cyber_security_ontology(ontology_name: Optional[str] = None) -> str:
    """
    Read cyber security ontology files from the module's ontologies directory.
    
    Args:
        ontology_name: Specific ontology to read (ThreatLandscape, VulnerabilityManagement, SecurityControls)
                      If None, returns list of available ontologies.
    
    Returns:
        Content of the ontology file(s) or list of available ontologies
    """
    try:
        # Get the directory of this module
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ontologies_dir = os.path.join(os.path.dirname(current_dir), "ontologies")
        
        if not os.path.exists(ontologies_dir):
            return f"❌ Ontologies directory not found at: {ontologies_dir}"
        
        # Get all TTL files
        ttl_files = glob.glob(os.path.join(ontologies_dir, "*.ttl"))
        
        if not ttl_files:
            return "❌ No ontology files (.ttl) found in the ontologies directory"
        
        # If no specific ontology requested, list available ones
        if ontology_name is None:
            available = []
            for file_path in ttl_files:
                filename = os.path.basename(file_path)
                name = filename.replace('.ttl', '')
                available.append(f"📋 {name}: {filename}")
            
            return "🔍 Available Cyber Security Ontologies:\n\n" + "\n".join(available) + "\n\nUse the ontology name (without .ttl) to read a specific ontology."
        
        # Find the specific ontology file
        target_file = None
        for file_path in ttl_files:
            filename = os.path.basename(file_path)
            if ontology_name.lower() in filename.lower():
                target_file = file_path
                break
        
        if target_file is None:
            available_names = [os.path.basename(f).replace('.ttl', '') for f in ttl_files]
            return f"❌ Ontology '{ontology_name}' not found. Available ontologies: {', '.join(available_names)}"
        
        # Read the ontology file
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        filename = os.path.basename(target_file)
        return f"📖 **{filename}**\n\n```turtle\n{content}\n```"
        
    except Exception as e:
        return f"❌ Error reading ontology: {str(e)}"

def search_cyber_security_ontologies(search_term: str, ontology_name: Optional[str] = None) -> str:
    """
    Search for terms within cyber security ontology files.
    
    Args:
        search_term: Term to search for
        ontology_name: Specific ontology to search in (optional)
    
    Returns:
        Search results with context
    """
    try:
        # Get the directory of this module
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ontologies_dir = os.path.join(os.path.dirname(current_dir), "ontologies")
        
        if not os.path.exists(ontologies_dir):
            return f"❌ Ontologies directory not found at: {ontologies_dir}"
        
        # Get TTL files to search
        ttl_files = glob.glob(os.path.join(ontologies_dir, "*.ttl"))
        
        if ontology_name:
            # Filter to specific ontology
            ttl_files = [f for f in ttl_files if ontology_name.lower() in os.path.basename(f).lower()]
            if not ttl_files:
                return f"❌ Ontology '{ontology_name}' not found"
        
        if not ttl_files:
            return "❌ No ontology files found to search"
        
        results: List[Dict[str, Any]] = []
        search_lower = search_term.lower()
        
        for file_path in ttl_files:
            filename = os.path.basename(file_path)
            matches: List[Dict[str, Any]] = []
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    if search_lower in line.lower():
                        # Get some context (previous and next lines)
                        context_start = max(0, line_num - 2)
                        context_end = min(len(lines), line_num + 2)
                        context_lines = lines[context_start:context_end]
                        
                        context = ""
                        for i, ctx_line in enumerate(context_lines):
                            actual_line_num = context_start + i + 1
                            prefix = ">>> " if actual_line_num == line_num else "    "
                            context += f"{prefix}{actual_line_num:3d}: {ctx_line.rstrip()}\n"
                        
                        matches.append({
                            'line': line_num,
                            'content': line.strip(),
                            'context': context
                        })
            
            except Exception:
                continue
            
            if matches:
                results.append({
                    'file': filename,
                    'matches': matches
                })
        
        if not results:
            return f"🔍 No matches found for '{search_term}' in the ontologies"
        
        # Format results
        output: list[str] = [f"🔍 **Search Results for '{search_term}'**\n"]
        
        for result in results:
            output.append(f"📋 **{result['file']}** ({len(result['matches'])} matches)")
            
            for i, match in enumerate(result['matches'][:5]):  # Limit to first 5 matches per file
                output.append(f"\n**Match {i+1} (Line {match['line']}):**")
                output.append(f"```turtle\n{match['context']}```")
            
            if len(result['matches']) > 5:
                output.append(f"\n... and {len(result['matches']) - 5} more matches in this file")
            
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ Error searching ontologies: {str(e)}"

def create_agent(
    agent_shared_state: Optional[AgentSharedState] = None,
    agent_configuration: Optional[AgentConfiguration] = None
) -> Agent:
    """Create Cyber Security Analyst Expert Agent"""
    # Initialize model
    model = ChatOpenAI(
        model=MODEL,
        temperature=TEMPERATURE,
        api_key=SecretStr(secret.get("OPENAI_API_KEY"))
    )

    # Use provided configuration or create default one
    if agent_configuration is None:
        agent_configuration = AgentConfiguration(system_prompt=SYSTEM_PROMPT)

    # Use provided shared state or create new one
    if agent_shared_state is None:
        agent_shared_state = AgentSharedState()

    # Initialize tools with cyber security specific capabilities
    tools: list = []
    
    # Add ontology reading tools
    read_ontology_tool = StructuredTool(
        name="read_cyber_security_ontology",
        description="Read cyber security ontology files (ThreatLandscape, VulnerabilityManagement, SecurityControls) to access specialized knowledge about threats, vulnerabilities, and security controls",
        func=read_cyber_security_ontology,
        args_schema=ReadOntologySchema
    )
    tools.append(read_ontology_tool)
    
    search_ontology_tool = StructuredTool(
        name="search_cyber_security_ontologies", 
        description="Search for specific terms within cyber security ontologies to find relevant threat intelligence, vulnerability information, or security control details",
        func=search_cyber_security_ontologies,
        args_schema=SearchOntologySchema
    )
    tools.append(search_ontology_tool)
    
    # TODO: Add additional cyber security specific tools here
    # - Vulnerability scanners
    # - Threat intelligence feeds  
    # - Security assessment tools
    # - Incident response workflows

    return CyberSecurityAnalystAgent(
        name=NAME,
        description=DESCRIPTION,
        chat_model=model,
        tools=tools,
        state=agent_shared_state,
        configuration=agent_configuration,
        memory=None,
    )

class CyberSecurityAnalystAgent(Agent):
    """Expert Cyber Security Analyst Agent"""
    pass
