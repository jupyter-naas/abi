"""
BFO Process Router Service

This service bridges the BFO (Basic Formal Ontology) process mapping research
with ABI's operational agent system. It enables intelligent process-based
agent selection and routing based on ontological knowledge.

The Process Router:
1. Maps user intents to BFO processes
2. Selects optimal agents based on process requirements
3. Orchestrates process execution with selected agents
4. Provides process analytics and optimization
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import requests
from datetime import datetime

from ..agent.Agent import Agent
from .process_mapping import ProcessMapper, ProcessType, ProcessContext, ModelEntity


class ProcessExecutionStatus(Enum):
    """Status of process execution"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProcessExecutionResult:
    """Result of process execution"""
    process_type: ProcessType
    selected_agent: str
    execution_time_ms: float
    status: ProcessExecutionStatus
    output: str
    metadata: Dict[str, Any]
    timestamp: datetime


class ProcessRouter:
    """
    BFO Process Router that integrates ontological process mapping with ABI agents.
    
    This service provides intelligent process-based agent selection by:
    1. Mapping user intents to BFO processes using ontological knowledge
    2. Selecting optimal agents based on process requirements and context
    3. Orchestrating process execution with the selected agents
    4. Providing analytics and optimization insights
    """
    
    def __init__(self, knowledge_graph_url: str = "http://localhost:7878"):
        self.knowledge_graph_url = knowledge_graph_url
        self.process_mapper = ProcessMapper()
        self.execution_history: List[ProcessExecutionResult] = []
        
        # Initialize BFO process mappings from knowledge graph
        self._load_bfo_mappings()
    
    def _load_bfo_mappings(self):
        """Load BFO process mappings from the knowledge graph"""
        try:
            # Query for BFO process definitions
            query = """
            PREFIX abi: <http://ontology.naas.ai/abi/>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_0000015>
            
            SELECT ?process ?processLabel ?capability ?agent WHERE {
                ?process a bfo:process .
                OPTIONAL { ?process rdfs:label ?processLabel }
                OPTIONAL { ?process abi:requiresCapability ?capability }
                OPTIONAL { ?agent abi:implementsProcess ?process }
            }
            """
            
            response = requests.post(
                f"{self.knowledge_graph_url}/query",
                data=query,
                headers={'Content-Type': 'application/sparql-query'},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                # Process the BFO mappings
                self._process_bfo_results(result)
                
        except Exception as e:
            print(f"Warning: Could not load BFO mappings from knowledge graph: {e}")
    
    def _process_bfo_results(self, sparql_result: Dict):
        """Process SPARQL results to build BFO mappings"""
        # This would parse the SPARQL results and build process mappings
        # For now, we'll use the default mappings from ProcessMapper
        pass
    
    def map_intent_to_process(self, user_intent: str, context: Optional[ProcessContext] = None) -> ProcessType:
        """
        Map a user intent to the most appropriate BFO process.
        
        Args:
            user_intent: The user's intent or request
            context: Optional context information for process selection
            
        Returns:
            The most appropriate BFO process type
        """
        # Use the knowledge graph to map intent to process
        try:
            # SPARQL query for intent-to-process mapping (commented out for now)
            # query = """
            # PREFIX abi: <http://ontology.naas.ai/abi/>
            # PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            # PREFIX bfo: <http://purl.obolibrary.org/obo/BFO_0000015>
            # 
            # SELECT ?process ?processLabel ?confidence WHERE {
            #     ?process a bfo:process .
            #     ?process rdfs:label ?processLabel .
            #     ?process abi:matchesIntent ?intent .
            #     FILTER(CONTAINS(LCASE(?intent), LCASE(?user_intent)))
            # }
            # ORDER BY DESC(?confidence)
            # LIMIT 1
            # """
            
            # For now, use a simple keyword-based mapping
            intent_lower = user_intent.lower()
            
            if any(word in intent_lower for word in ['code', 'program', 'develop', 'script']):
                return ProcessType.CODE_GENERATION
            elif any(word in intent_lower for word in ['image', 'picture', 'photo', 'visual']):
                return ProcessType.IMAGE_GENERATION
            elif any(word in intent_lower for word in ['analyze', 'examine', 'study', 'research']):
                return ProcessType.TECHNICAL_ANALYSIS
            elif any(word in intent_lower for word in ['write', 'create', 'generate', 'compose']):
                return ProcessType.CREATIVE_WRITING
            elif any(word in intent_lower for word in ['calculate', 'math', 'compute', 'solve']):
                return ProcessType.MATHEMATICAL_COMPUTATION
            elif any(word in intent_lower for word in ['search', 'find', 'look up']):
                return ProcessType.REAL_TIME_SEARCH
            elif any(word in intent_lower for word in ['translate', 'language']):
                return ProcessType.TRANSLATION
            elif any(word in intent_lower for word in ['summarize', 'summary']):
                return ProcessType.SUMMARIZATION
            else:
                return ProcessType.PROBLEM_SOLVING  # Default fallback
                
        except Exception as e:
            print(f"Error mapping intent to process: {e}")
            return ProcessType.PROBLEM_SOLVING
    
    def select_agent_for_process(
        self, 
        process_type: ProcessType, 
        available_agents: List[Agent],
        context: Optional[ProcessContext] = None
    ) -> Tuple[Agent, float]:
        """
        Select the optimal agent for a given process based on BFO mappings.
        
        Args:
            process_type: The BFO process type to execute
            available_agents: List of available ABI agents
            context: Optional context for agent selection
            
        Returns:
            Tuple of (selected_agent, confidence_score)
        """
        # Get optimal model from BFO process mapper
        optimal_model = self.process_mapper.get_optimal_model(process_type, context)
        
        if not optimal_model:
            # Fallback to first available agent
            return available_agents[0], 0.5
        
        # Map model to agent based on provider and capabilities
        best_agent = None
        best_score = 0.0
        
        for agent in available_agents:
            score = self._score_agent_for_process(agent, process_type, optimal_model)
            if score > best_score:
                best_score = score
                best_agent = agent
        
        if not best_agent:
            best_agent = available_agents[0]
            best_score = 0.5
        
        return best_agent, best_score
    
    def _score_agent_for_process(self, agent: Agent, process_type: ProcessType, optimal_model: ModelEntity) -> float:
        """
        Score an agent's suitability for a specific process.
        
        Args:
            agent: The ABI agent to score
            process_type: The process type to execute
            optimal_model: The optimal model from BFO mapping
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.0
        
        # Score based on agent name matching provider
        agent_name_lower = agent.name.lower()
        provider_lower = optimal_model.provider.lower()
        
        if provider_lower in agent_name_lower:
            score += 0.4
        
        # Score based on agent description matching process requirements
        agent_desc_lower = agent.description.lower()
        process_name_lower = process_type.value.lower()
        
        if process_name_lower in agent_desc_lower:
            score += 0.3
        
        # Score based on agent capabilities (if available)
        if hasattr(agent, 'capabilities'):
            for capability in optimal_model.capabilities:
                if capability.value.lower() in agent_desc_lower:
                    score += 0.2
        
        # Score based on agent specializations
        for specialization in optimal_model.specializations:
            if specialization.value.lower() in agent_desc_lower:
                score += 0.1
        
        return min(score, 1.0)
    
    def execute_process(
        self,
        user_intent: str,
        available_agents: List[Agent],
        context: Optional[ProcessContext] = None
    ) -> ProcessExecutionResult:
        """
        Execute a process using BFO-based agent selection.
        
        Args:
            user_intent: The user's intent or request
            available_agents: List of available ABI agents
            context: Optional context for process execution
            
        Returns:
            Process execution result with details
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Map intent to BFO process
            process_type = self.map_intent_to_process(user_intent, context)
            
            # Step 2: Select optimal agent
            selected_agent, confidence = self.select_agent_for_process(
                process_type, available_agents, context
            )
            
            # Step 3: Execute with selected agent
            output = selected_agent.invoke(user_intent)
            
            # Step 4: Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Step 5: Create result
            result = ProcessExecutionResult(
                process_type=process_type,
                selected_agent=selected_agent.name,
                execution_time_ms=execution_time,
                status=ProcessExecutionStatus.COMPLETED,
                output=output,
                metadata={
                    'confidence': confidence,
                    'user_intent': user_intent,
                    'available_agents': len(available_agents)
                },
                timestamp=start_time
            )
            
            # Step 6: Store in history
            self.execution_history.append(result)
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = ProcessExecutionResult(
                process_type=ProcessType.PROBLEM_SOLVING,
                selected_agent="unknown",
                execution_time_ms=execution_time,
                status=ProcessExecutionStatus.FAILED,
                output=str(e),
                metadata={'error': str(e)},
                timestamp=start_time
            )
            
            self.execution_history.append(result)
            return result
    
    def get_process_analytics(self) -> Dict[str, Any]:
        """
        Get analytics about process execution patterns.
        
        Returns:
            Dictionary with process analytics
        """
        if not self.execution_history:
            return {}
        
        # Process type distribution
        process_counts = {}
        agent_counts = {}
        total_execution_time = 0
        successful_executions = 0
        
        for result in self.execution_history:
            # Count process types
            process_name = result.process_type.value
            process_counts[process_name] = process_counts.get(process_name, 0) + 1
            
            # Count agents
            agent_counts[result.selected_agent] = agent_counts.get(result.selected_agent, 0) + 1
            
            # Track execution time
            total_execution_time += result.execution_time_ms
            
            # Track success rate
            if result.status == ProcessExecutionStatus.COMPLETED:
                successful_executions += 1
        
        return {
            'total_executions': len(self.execution_history),
            'successful_executions': successful_executions,
            'success_rate': successful_executions / len(self.execution_history),
            'average_execution_time_ms': total_execution_time / len(self.execution_history),
            'process_distribution': process_counts,
            'agent_distribution': agent_counts,
            'most_used_process': max(process_counts.items(), key=lambda x: x[1])[0] if process_counts else None,
            'most_used_agent': max(agent_counts.items(), key=lambda x: x[1])[0] if agent_counts else None
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """
        Get suggestions for optimizing process execution based on analytics.
        
        Returns:
            List of optimization suggestions
        """
        analytics = self.get_process_analytics()
        suggestions = []
        
        if not analytics:
            return ["No execution data available for optimization suggestions"]
        
        # Check for process type imbalances
        process_dist = analytics.get('process_distribution', {})
        if process_dist:
            most_used = max(process_dist.values())
            least_used = min(process_dist.values())
            
            if most_used > least_used * 3:
                suggestions.append(
                    f"Consider balancing process usage: {most_used} vs {least_used} executions"
                )
        
        # Check for agent imbalances
        agent_dist = analytics.get('agent_distribution', {})
        if agent_dist:
            most_used_agent = max(agent_dist.values())
            total_executions = analytics['total_executions']
            
            if most_used_agent > total_executions * 0.7:
                suggestions.append(
                    f"Agent {max(agent_dist.items(), key=lambda x: x[1])[0]} is used {most_used_agent/total_executions*100:.1f}% of the time - consider diversifying"
                )
        
        # Check execution time
        avg_time = analytics.get('average_execution_time_ms', 0)
        if avg_time > 5000:  # 5 seconds
            suggestions.append(
                f"Average execution time is {avg_time:.0f}ms - consider optimizing agent selection for faster processes"
            )
        
        # Check success rate
        success_rate = analytics.get('success_rate', 0)
        if success_rate < 0.9:
            suggestions.append(
                f"Success rate is {success_rate*100:.1f}% - consider improving error handling and agent selection"
            )
        
        return suggestions
