"""Process Router Service - BFO AI Process Network Implementation.

This module implements the Process Router Service as an "operational bridge" between
intent mapping and agent selection, based on the BFO AI Process Network concept.

The Process Router:
1. Identifies processes from user requests
2. Maps processes to required capabilities
3. Routes to optimal agents based on capability requirements
4. Provides cost and performance information

This transforms AI from a model-selection problem into a process-completion problem.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import requests
from abi import logger


class ProcessType(Enum):
    """BFO-based process types for AI task classification."""
    ANALYSIS = "analysis"
    CREATION = "creation"
    RESEARCH = "research"
    CALCULATION = "calculation"
    VISUALIZATION = "visualization"
    TRANSLATION = "translation"
    OPTIMIZATION = "optimization"
    VALIDATION = "validation"


class CapabilityType(Enum):
    """Capability types that AI agents can provide."""
    TEXT_GENERATION = "text_generation"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    IMAGE_GENERATION = "image_generation"
    WEB_SEARCH = "web_search"
    MATHEMATICAL_REASONING = "mathematical_reasoning"
    LOGICAL_REASONING = "logical_reasoning"
    CREATIVE_WRITING = "creative_writing"
    TECHNICAL_WRITING = "technical_writing"
    MULTIMODAL_ANALYSIS = "multimodal_analysis"
    RESEARCH = "research"
    TRANSLATION = "translation"
    CALCULATION = "calculation"
    VISUALIZATION = "visualization"


@dataclass
class ProcessCapability:
    """Maps a process to its required capabilities."""
    process: str
    capabilities: List[CapabilityType]
    description: str
    complexity: str  # "simple", "moderate", "complex"


@dataclass
class AgentRecommendation:
    """Agent recommendation with capability match and cost information."""
    agent_name: str
    agent_label: str
    matched_capabilities: List[str]
    cost_per_million_tokens: Optional[str]
    description: Optional[str]
    confidence_score: float


class ProcessRouter:
    """Process Router Service implementing BFO AI Process Network."""
    
    def __init__(self, oxigraph_url: str = "http://localhost:7878"):
        self.oxigraph_url = oxigraph_url
        self.process_capabilities = self._initialize_process_capabilities()
    
    def _initialize_process_capabilities(self) -> Dict[str, ProcessCapability]:
        """Initialize process-to-capability mappings."""
        return {
            "business proposal": ProcessCapability(
                process="business proposal",
                capabilities=[
                    CapabilityType.RESEARCH,
                    CapabilityType.CREATIVE_WRITING,
                    CapabilityType.TECHNICAL_WRITING,
                    CapabilityType.DATA_ANALYSIS,
                    CapabilityType.VISUALIZATION
                ],
                description="Create comprehensive business proposals with market analysis, financial projections, and professional presentation",
                complexity="complex"
            ),
            "code generation": ProcessCapability(
                process="code generation",
                capabilities=[
                    CapabilityType.CODE_GENERATION,
                    CapabilityType.LOGICAL_REASONING,
                    CapabilityType.TECHNICAL_WRITING
                ],
                description="Generate code in various programming languages with best practices",
                complexity="moderate"
            ),
            "data analysis": ProcessCapability(
                process="data analysis",
                capabilities=[
                    CapabilityType.DATA_ANALYSIS,
                    CapabilityType.MATHEMATICAL_REASONING,
                    CapabilityType.VISUALIZATION
                ],
                description="Analyze data sets, create visualizations, and extract insights",
                complexity="moderate"
            ),
            "image generation": ProcessCapability(
                process="image generation",
                capabilities=[
                    CapabilityType.IMAGE_GENERATION,
                    CapabilityType.CREATIVE_WRITING
                ],
                description="Generate images from text descriptions",
                complexity="simple"
            ),
            "web search": ProcessCapability(
                process="web search",
                capabilities=[
                    CapabilityType.WEB_SEARCH,
                    CapabilityType.RESEARCH
                ],
                description="Search the web for current information and research",
                complexity="simple"
            ),
            "translation": ProcessCapability(
                process="translation",
                capabilities=[
                    CapabilityType.TEXT_GENERATION,
                    CapabilityType.TRANSLATION
                ],
                description="Translate text between different languages",
                complexity="simple"
            ),
            "mathematical calculation": ProcessCapability(
                process="mathematical calculation",
                capabilities=[
                    CapabilityType.MATHEMATICAL_REASONING,
                    CapabilityType.CALCULATION
                ],
                description="Perform complex mathematical calculations and reasoning",
                complexity="moderate"
            ),
            "creative writing": ProcessCapability(
                process="creative writing",
                capabilities=[
                    CapabilityType.CREATIVE_WRITING,
                    CapabilityType.TEXT_GENERATION
                ],
                description="Generate creative content, stories, and artistic text",
                complexity="moderate"
            ),
            "technical writing": ProcessCapability(
                process="technical writing",
                capabilities=[
                    CapabilityType.TECHNICAL_WRITING,
                    CapabilityType.TEXT_GENERATION
                ],
                description="Create technical documentation, reports, and manuals",
                complexity="moderate"
            ),
            "multimodal analysis": ProcessCapability(
                process="multimodal analysis",
                capabilities=[
                    CapabilityType.MULTIMODAL_ANALYSIS,
                    CapabilityType.DATA_ANALYSIS,
                    CapabilityType.VISUALIZATION
                ],
                description="Analyze images, videos, and other multimodal content",
                complexity="complex"
            )
        }
    
    def identify_process(self, user_request: str) -> Optional[str]:
        """Identify the process from user request using keyword matching."""
        user_request_lower = user_request.lower()
        
        # Direct process matching
        for process in self.process_capabilities.keys():
            if process in user_request_lower:
                return process
        
        # Keyword-based process identification
        keywords_to_process = {
            "proposal": "business proposal",
            "business plan": "business proposal",
            "code": "code generation",
            "programming": "code generation",
            "develop": "code generation",
            "analyze data": "data analysis",
            "data": "data analysis",
            "chart": "data analysis",
            "visualize": "data analysis",
            "image": "image generation",
            "picture": "image generation",
            "generate image": "image generation",
            "create image": "image generation",
            "search": "web search",
            "find": "web search",
            "look up": "web search",
            "translate": "translation",
            "language": "translation",
            "calculate": "mathematical calculation",
            "math": "mathematical calculation",
            "compute": "mathematical calculation",
            "write": "creative writing",
            "story": "creative writing",
            "creative": "creative writing",
            "document": "technical writing",
            "manual": "technical writing",
            "technical": "technical writing",
            "video": "multimodal analysis",
            "multimodal": "multimodal analysis",
            "visual": "multimodal analysis"
        }
        
        for keyword, process in keywords_to_process.items():
            if keyword in user_request_lower:
                return process
        
        return None
    
    def get_process_capabilities(self, process: str) -> Optional[ProcessCapability]:
        """Get capabilities required for a specific process."""
        return self.process_capabilities.get(process)
    
    def query_agents_by_capabilities(self, capabilities: List[CapabilityType]) -> List[Dict[str, Any]]:
        """Query Oxigraph for agents that match the required capabilities."""
        capability_names = [cap.value for cap in capabilities]
        
        # Build agent name matching conditions based on capabilities
        agent_conditions = []
        for cap in capability_names:
            if cap == "code_generation":
                agent_conditions.append('CONTAINS(?agentLabel, "Code") || CONTAINS(?agentLabel, "Programming")')
            elif cap == "data_analysis":
                agent_conditions.append('CONTAINS(?agentLabel, "Analysis") || CONTAINS(?agentLabel, "Data")')
            elif cap == "image_generation":
                agent_conditions.append('CONTAINS(?agentLabel, "Image") || CONTAINS(?agentLabel, "Visual") || CONTAINS(?agentLabel, "Multimodal")')
            elif cap == "web_search":
                agent_conditions.append('CONTAINS(?agentLabel, "Search") || CONTAINS(?agentLabel, "Perplexity")')
            elif cap == "mathematical_reasoning":
                agent_conditions.append('CONTAINS(?agentLabel, "Calculation") || CONTAINS(?agentLabel, "Math") || CONTAINS(?agentLabel, "Reasoning")')
            elif cap == "creative_writing":
                agent_conditions.append('CONTAINS(?agentLabel, "Creative") || CONTAINS(?agentLabel, "Story") || CONTAINS(?agentLabel, "Text")')
            elif cap == "technical_writing":
                agent_conditions.append('CONTAINS(?agentLabel, "Technical") || CONTAINS(?agentLabel, "Documentation") || CONTAINS(?agentLabel, "Text")')
            elif cap == "multimodal_analysis":
                agent_conditions.append('CONTAINS(?agentLabel, "Multimodal") || CONTAINS(?agentLabel, "Image") || CONTAINS(?agentLabel, "Video")')
            elif cap == "translation":
                agent_conditions.append('CONTAINS(?agentLabel, "Translation") || CONTAINS(?agentLabel, "Language")')
            elif cap == "research":
                agent_conditions.append('CONTAINS(?agentLabel, "Research") || CONTAINS(?agentLabel, "Analysis") || CONTAINS(?agentLabel, "Perplexity")')
            elif cap == "visualization":
                agent_conditions.append('CONTAINS(?agentLabel, "Visual") || CONTAINS(?agentLabel, "Image") || CONTAINS(?agentLabel, "Chart")')
            elif cap == "calculation":
                agent_conditions.append('CONTAINS(?agentLabel, "Calculation") || CONTAINS(?agentLabel, "Math")')
            elif cap == "logical_reasoning":
                agent_conditions.append('CONTAINS(?agentLabel, "Reasoning") || CONTAINS(?agentLabel, "Logic")')
            elif cap == "text_generation":
                agent_conditions.append('CONTAINS(?agentLabel, "Text") || CONTAINS(?agentLabel, "Writing") || CONTAINS(?agentLabel, "Creative")')
        
        # If no specific conditions, return all agents
        agent_filter = " || ".join(agent_conditions) if agent_conditions else "true"
        
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        
        SELECT DISTINCT ?agent ?agentLabel ?role ?description WHERE {{
            ?agent a abi:AIAgent .
            ?agent rdfs:label ?agentLabel .
            
            # Get specialized roles
            OPTIONAL {{ ?agent abi:hasSpecializedRole ?role }}
            
            # Get description
            OPTIONAL {{ ?agent rdfs:comment ?description }}
            
            # Filter for agents matching capabilities
            FILTER({agent_filter})
            
            # Filter out ABI internal agents (except connector)
            FILTER(!CONTAINS(?agentLabel, "ABI ") || CONTAINS(?agentLabel, "ABI Connector"))
            
            # Ensure we have a valid agent label
            FILTER(BOUND(?agentLabel))
        }}
        ORDER BY 
            # Prioritize agents with "Agent" in name (actual AI models)
            DESC(CONTAINS(?agentLabel, "Agent"))
            # Then by name
            ?agentLabel
        """
        
        try:
            response = requests.post(
                f"{self.oxigraph_url}/query",
                data=query,
                headers={"Content-Type": "application/sparql-query"}
            )
            response.raise_for_status()
            
            results = response.json()
            return results.get("results", {}).get("bindings", [])
        except Exception as e:
            logger.error(f"Error querying Oxigraph: {e}")
            return []
    
    def recommend_agents_for_process(self, user_request: str) -> Dict[str, Any]:
        """Main method to recommend agents for a user request based on process analysis."""
        # Step 1: Identify the process
        process = self.identify_process(user_request)
        
        if not process:
            return {
                "success": False,
                "error": "Could not identify a specific process from your request",
                "suggestion": "Try being more specific about what you want to accomplish"
            }
        
        # Step 2: Get process capabilities
        process_capability = self.get_process_capabilities(process)
        if not process_capability:
            return {
                "success": False,
                "error": f"Process '{process}' not found in capability mapping"
            }
        
        # Step 3: Query agents with matching capabilities
        matching_agents = self.query_agents_by_capabilities(process_capability.capabilities)
        
        if not matching_agents:
            return {
                "success": False,
                "error": f"No agents found with capabilities for '{process}'",
                "process": process,
                "required_capabilities": [cap.value for cap in process_capability.capabilities]
            }
        
        # Step 4: Process and rank recommendations
        recommendations = []
        for agent_data in matching_agents:
            agent_label = agent_data.get("agentLabel", {}).get("value", "Unknown Agent")
            capability = agent_data.get("capability", {}).get("value", "Unknown")
            cost = agent_data.get("cost", {}).get("value", "Unknown")
            description = agent_data.get("description", {}).get("value", "")
            
            # Calculate confidence score based on capability match
            confidence = 1.0 if capability in [cap.value for cap in process_capability.capabilities] else 0.5
            
            recommendation = AgentRecommendation(
                agent_name=agent_label,
                agent_label=agent_label,
                matched_capabilities=[capability],
                cost_per_million_tokens=cost,
                description=description,
                confidence_score=confidence
            )
            recommendations.append(recommendation)
        
        # Sort by confidence score
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return {
            "success": True,
            "process": process,
            "process_description": process_capability.description,
            "complexity": process_capability.complexity,
            "required_capabilities": [cap.value for cap in process_capability.capabilities],
            "recommendations": [
                {
                    "agent_name": rec.agent_name,
                    "agent_label": rec.agent_label,
                    "matched_capabilities": rec.matched_capabilities,
                    "cost_per_million_tokens": rec.cost_per_million_tokens,
                    "description": rec.description,
                    "confidence_score": rec.confidence_score
                }
                for rec in recommendations[:10]  # Top 10 recommendations
            ],
            "total_agents_found": len(matching_agents)
        }
    
    def get_process_costs(self, process: str) -> Dict[str, Any]:
        """Get cost information for agents that can handle a specific process."""
        process_capability = self.get_process_capabilities(process)
        if not process_capability:
            return {"success": False, "error": f"Process '{process}' not found"}
        
        matching_agents = self.query_agents_by_capabilities(process_capability.capabilities)
        
        cost_analysis = {
            "process": process,
            "complexity": process_capability.complexity,
            "agents": [],
            "cost_summary": {
                "lowest_cost": None,
                "highest_cost": None,
                "average_cost": None
            }
        }
        
        costs = []
        for agent_data in matching_agents:
            agent_label = agent_data.get("agentLabel", {}).get("value", "Unknown")
            cost = agent_data.get("cost", {}).get("value", "Unknown")
            description = agent_data.get("description", {}).get("value", "")
            
            cost_analysis["agents"].append({
                "agent_name": agent_label,
                "cost": cost,
                "description": description
            })
            
            # Try to extract numeric cost for analysis
            if cost != "Unknown" and cost != "Free":
                try:
                    # Extract numeric value from cost string
                    import re
                    cost_match = re.search(r'[\d.]+', cost)
                    if cost_match:
                        costs.append(float(cost_match.group()))
                except Exception:
                    pass
        
        if costs:
            cost_analysis["cost_summary"] = {
                "lowest_cost": min(costs),
                "highest_cost": max(costs),
                "average_cost": sum(costs) / len(costs)
            }
        
        return cost_analysis
