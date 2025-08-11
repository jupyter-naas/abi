"""
Enhanced Intent Mapper with BFO Process Integration

This enhanced intent mapper combines traditional intent mapping with
BFO (Basic Formal Ontology) process routing for intelligent agent selection.
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from .IntentMapper import IntentMapper, Intent, IntentType

from ...process_router.ProcessRouter import ProcessRouter, ProcessType, ProcessContext
from ..Agent import Agent


class IntentMappingStrategy(Enum):
    """Strategy for intent mapping"""
    TRADITIONAL = "traditional"  # Use original IntentMapper
    BFO_PROCESS = "bfo_process"  # Use BFO process routing
    HYBRID = "hybrid"  # Combine both approaches


@dataclass
class EnhancedIntentResult:
    """Enhanced intent mapping result"""
    intent: Intent
    process_type: Optional[ProcessType]
    confidence: float
    strategy: IntentMappingStrategy
    metadata: Dict[str, Any]


class EnhancedIntentMapper:
    """
    Enhanced Intent Mapper that combines traditional intent mapping with BFO process routing.
    
    This mapper provides intelligent agent selection by:
    1. Using traditional vector-based intent mapping for basic intent recognition
    2. Integrating BFO process routing for optimal agent selection
    3. Providing hybrid mapping that combines both approaches
    """
    
    def __init__(
        self, 
        intents: List[Intent],
        strategy: IntentMappingStrategy = IntentMappingStrategy.HYBRID,
        knowledge_graph_url: str = "http://localhost:7878"
    ):
        self.intents = intents
        self.strategy = strategy
        
        # Initialize traditional intent mapper
        self.traditional_mapper = IntentMapper(intents)
        
        # Initialize BFO process router
        self.process_router = ProcessRouter(knowledge_graph_url)
        
        # Enhanced system prompt for hybrid mapping
        self.enhanced_system_prompt = """
You are an enhanced intent mapper that combines traditional intent recognition with BFO process understanding.

Your task is to:
1. Identify the user's intent
2. Map it to the most appropriate BFO process type
3. Provide confidence scores for both mappings

For BFO process mapping, consider these categories:
- CODE_GENERATION: Programming, development, scripting
- IMAGE_GENERATION: Visual content, images, graphics
- TECHNICAL_ANALYSIS: Analysis, examination, research
- CREATIVE_WRITING: Writing, content creation, storytelling
- MATHEMATICAL_COMPUTATION: Calculations, math, computations
- REAL_TIME_SEARCH: Search, lookup, information retrieval
- TRANSLATION: Language translation, localization
- SUMMARIZATION: Summarizing, condensing, extracting key points
- PROBLEM_SOLVING: General problem solving, troubleshooting

Respond with: INTENT|PROCESS_TYPE|CONFIDENCE
Example: "write a report|CREATIVE_WRITING|0.85"
"""
    
    def map_intent_enhanced(
        self, 
        prompt: str, 
        context: Optional[ProcessContext] = None,
        k: int = 1
    ) -> List[EnhancedIntentResult]:
        """
        Enhanced intent mapping that combines traditional and BFO approaches.
        
        Args:
            prompt: User prompt
            context: Optional process context
            k: Number of results to return
            
        Returns:
            List of enhanced intent results
        """
        results = []
        
        if self.strategy in [IntentMappingStrategy.TRADITIONAL, IntentMappingStrategy.HYBRID]:
            # Get traditional intent mapping
            traditional_results = self.traditional_mapper.map_prompt(prompt, k)
            
            for result in traditional_results[0]:  # Use intent-based results
                if 'intent' in result and result['intent']:
                    enhanced_result = EnhancedIntentResult(
                        intent=result['intent'],
                        process_type=None,
                        confidence=result.get('score', 0.5),
                        strategy=IntentMappingStrategy.TRADITIONAL,
                        metadata={'traditional_score': result.get('score', 0.5)}
                    )
                    results.append(enhanced_result)
        
        if self.strategy in [IntentMappingStrategy.BFO_PROCESS, IntentMappingStrategy.HYBRID]:
            # Get BFO process mapping
            try:
                process_type = self.process_router.map_intent_to_process(prompt, context)
                
                # Create a synthetic intent for the process
                process_intent = Intent(
                    intent_value=f"execute_{process_type.value}",
                    intent_type=IntentType.AGENT,
                    intent_target=process_type
                )
                
                enhanced_result = EnhancedIntentResult(
                    intent=process_intent,
                    process_type=process_type,
                    confidence=0.8,  # High confidence for BFO mapping
                    strategy=IntentMappingStrategy.BFO_PROCESS,
                    metadata={'process_type': process_type.value}
                )
                results.append(enhanced_result)
                
            except Exception as e:
                print(f"Error in BFO process mapping: {e}")
        
        # Sort by confidence and return top k
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:k]
    
    def select_agent_enhanced(
        self,
        prompt: str,
        available_agents: List[Agent],
        context: Optional[ProcessContext] = None
    ) -> Tuple[Agent, float, Dict[str, Any]]:
        """
        Enhanced agent selection using both intent and process mapping.
        
        Args:
            prompt: User prompt
            available_agents: List of available agents
            context: Optional process context
            
        Returns:
            Tuple of (selected_agent, confidence, metadata)
        """
        # Get enhanced intent mapping
        intent_results = self.map_intent_enhanced(prompt, context, k=3)
        
        if not intent_results:
            # Fallback to first available agent
            return available_agents[0], 0.5, {'strategy': 'fallback'}
        
        best_agent = None
        best_confidence = 0.0
        best_metadata = {}
        
        for result in intent_results:
            if result.process_type:
                # Use BFO process routing
                try:
                    agent, confidence = self.process_router.select_agent_for_process(
                        result.process_type, available_agents, context
                    )
                    
                    if confidence > best_confidence:
                        best_agent = agent
                        best_confidence = confidence
                        best_metadata = {
                            'strategy': 'bfo_process',
                            'process_type': result.process_type.value,
                            'intent': result.intent.intent_value
                        }
                        
                except Exception as e:
                    print(f"Error in BFO agent selection: {e}")
            
            else:
                # Use traditional intent-based selection
                # Find agent that matches the intent
                for agent in available_agents:
                    agent_score = self._score_agent_for_intent(agent, result.intent)
                    
                    if agent_score > best_confidence:
                        best_agent = agent
                        best_confidence = agent_score
                        best_metadata = {
                            'strategy': 'traditional_intent',
                            'intent': result.intent.intent_value
                        }
        
        if not best_agent:
            best_agent = available_agents[0]
            best_confidence = 0.5
            best_metadata = {'strategy': 'fallback'}
        
        return best_agent, best_confidence, best_metadata
    
    def _score_agent_for_intent(self, agent: Agent, intent: Intent) -> float:
        """
        Score an agent's suitability for a specific intent.
        
        Args:
            agent: The agent to score
            intent: The intent to match
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        score = 0.0
        
        # Score based on agent name matching intent
        agent_name_lower = agent.name.lower()
        intent_lower = intent.intent_value.lower()
        
        if intent_lower in agent_name_lower:
            score += 0.4
        
        # Score based on agent description matching intent
        agent_desc_lower = agent.description.lower()
        
        if intent_lower in agent_desc_lower:
            score += 0.3
        
        # Score based on intent type matching agent capabilities
        if intent.intent_type == IntentType.AGENT:
            score += 0.2
        
        # Score based on intent target (if available)
        if intent.intent_target and hasattr(agent, 'capabilities'):
            target_str = str(intent.intent_target).lower()
            if target_str in agent_desc_lower:
                score += 0.1
        
        return min(score, 1.0)
    
    def execute_with_enhanced_routing(
        self,
        prompt: str,
        available_agents: List[Agent],
        context: Optional[ProcessContext] = None
    ) -> Dict[str, Any]:
        """
        Execute a prompt using enhanced intent and process routing.
        
        Args:
            prompt: User prompt
            available_agents: List of available agents
            context: Optional process context
            
        Returns:
            Execution result with metadata
        """
        # Select optimal agent using enhanced routing
        selected_agent, confidence, metadata = self.select_agent_enhanced(
            prompt, available_agents, context
        )
        
        # Execute with selected agent
        try:
            output = selected_agent.invoke(prompt)
            
            return {
                'success': True,
                'output': output,
                'selected_agent': selected_agent.name,
                'confidence': confidence,
                'metadata': metadata,
                'strategy': metadata.get('strategy', 'unknown')
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'selected_agent': selected_agent.name if selected_agent else None,
                'confidence': confidence,
                'metadata': metadata,
                'strategy': metadata.get('strategy', 'unknown')
            }
    
    def get_routing_analytics(self) -> Dict[str, Any]:
        """
        Get analytics about enhanced routing performance.
        
        Returns:
            Dictionary with routing analytics
        """
        # Combine analytics from both traditional mapper and process router
        traditional_analytics = {
            'intent_mappings': len(self.intents),
            'strategy': 'traditional'
        }
        
        process_analytics = self.process_router.get_process_analytics()
        process_analytics['strategy'] = 'bfo_process'
        
        return {
            'traditional': traditional_analytics,
            'bfo_process': process_analytics,
            'hybrid_strategy': self.strategy.value
        }
