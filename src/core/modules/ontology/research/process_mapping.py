"""
BFO-Based Process Mapping System

This module implements the Basic Formal Ontology (BFO) 7 buckets framework
for process-centric AI model routing and selection.

Based on BFO methodology:
- Material Entities (WHAT/WHO): AI models, infrastructure, users
- Qualities (HOW-IT-IS): Intelligence, speed, cost, capabilities
- Realizable Entities (WHY-POTENTIAL): Model capabilities and functions
- Processes (HOW-IT-HAPPENS): Cognitive processes to be executed
- Temporal Regions (WHEN): Timing, availability, scheduling
- Spatial Regions (WHERE): Deployment locations, endpoints
- Information Content Entities (HOW-WE-KNOW): Documentation, metrics, outputs
"""

from enum import Enum
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from pydantic import BaseModel


class ProcessType(Enum):
    """
    Cognitive processes that can be performed by AI models.
    Organized by BFO Process category (HOW-IT-HAPPENS).
    """
    
    # Analysis Processes
    TRUTH_SEEKING_ANALYSIS = "truth_seeking_analysis"
    ETHICAL_ANALYSIS = "ethical_analysis"
    TECHNICAL_ANALYSIS = "technical_analysis"
    MARKET_ANALYSIS = "market_analysis"
    DATA_ANALYSIS = "data_analysis"
    DOCUMENT_ANALYSIS = "document_analysis"
    
    # Creative Processes
    IMAGE_GENERATION = "image_generation"
    CREATIVE_WRITING = "creative_writing"
    BRAINSTORMING = "brainstorming"
    STORYTELLING = "storytelling"
    CONTENT_CREATION = "content_creation"
    
    # Technical Processes
    CODE_GENERATION = "code_generation"
    MATHEMATICAL_COMPUTATION = "mathematical_computation"
    SYSTEM_DESIGN = "system_design"
    DEBUGGING = "debugging"
    ALGORITHM_DEVELOPMENT = "algorithm_development"
    
    # Information Processes
    REAL_TIME_SEARCH = "real_time_search"
    RESEARCH_SYNTHESIS = "research_synthesis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    FACT_CHECKING = "fact_checking"
    
    # Communication Processes
    INSTRUCTION_FOLLOWING = "instruction_following"
    CONVERSATION_MANAGEMENT = "conversation_management"
    EXECUTIVE_COMMUNICATION = "executive_communication"
    TECHNICAL_DOCUMENTATION = "technical_documentation"
    CUSTOMER_SUPPORT = "customer_support"
    
    # Reasoning Processes
    LOGICAL_REASONING = "logical_reasoning"
    CAUSAL_REASONING = "causal_reasoning"
    ANALOGICAL_REASONING = "analogical_reasoning"
    STRATEGIC_PLANNING = "strategic_planning"
    PROBLEM_SOLVING = "problem_solving"


class ModelCapability(Enum):
    """
    Realizable Entities (WHY-POTENTIAL): What models can potentially do.
    """
    
    TRUTH_SEEKING = "truth_seeking"
    ETHICAL_REASONING = "ethical_reasoning"
    MULTIMODAL_PROCESSING = "multimodal_processing"
    CODE_GENERATION = "code_generation"
    MATHEMATICAL_REASONING = "mathematical_reasoning"
    REAL_TIME_SEARCH = "real_time_search"
    IMAGE_GENERATION = "image_generation"
    INSTRUCTION_FOLLOWING = "instruction_following"
    CREATIVE_WRITING = "creative_writing"
    TECHNICAL_ANALYSIS = "technical_analysis"
    DOCUMENT_PROCESSING = "document_processing"
    MULTILINGUAL_SUPPORT = "multilingual_support"
    WEB_BROWSING = "web_browsing"
    LIVE_DATA_ACCESS = "live_data_access"
    CONSTITUTIONAL_AI = "constitutional_ai"
    SCIENTIFIC_REASONING = "scientific_reasoning"


class ModelQualities(BaseModel):
    """
    Qualities (HOW-IT-IS): Properties that inhere in AI models.
    """
    
    intelligence_score: int  # 0-100 scale
    speed_tokens_per_sec: float
    cost_per_million_tokens: float
    context_window_tokens: int
    latency_first_token_ms: float
    reliability_uptime_percent: float
    safety_rating: int  # 1-10 scale
    
    # Derived quality metrics
    @property
    def price_performance_ratio(self) -> float:
        """Intelligence per dollar spent"""
        return self.intelligence_score / self.cost_per_million_tokens
    
    @property
    def speed_intelligence_ratio(self) -> float:
        """Intelligence per second of processing"""
        return self.intelligence_score / (1000 / self.speed_tokens_per_sec)


class ModelEntity(BaseModel):
    """
    Material Entity (WHAT/WHO): The AI model itself.
    """
    
    name: str
    provider: str
    model_id: str
    api_endpoint: str
    qualities: ModelQualities
    capabilities: List[ModelCapability]
    specializations: List[ProcessType]
    
    # Spatial (WHERE) and Temporal (WHEN) properties
    deployment_regions: List[str]
    availability_hours: str
    data_sovereignty: str


class ProcessRequirements(BaseModel):
    """
    Requirements for executing a specific cognitive process.
    """
    
    required_capabilities: List[ModelCapability]
    minimum_intelligence: int
    maximum_cost_per_token: Optional[float] = None
    minimum_context_window: Optional[int] = None
    maximum_latency_ms: Optional[float] = None
    require_real_time: bool = False
    require_data_sovereignty: Optional[str] = None
    
    # Quality weights for model selection (0-1 scale)
    intelligence_weight: float = 0.4
    speed_weight: float = 0.2
    cost_weight: float = 0.2
    reliability_weight: float = 0.1
    safety_weight: float = 0.1


class ProcessContext(BaseModel):
    """
    Context information for process execution.
    """
    
    user_preferences: Dict[str, Union[str, int, float]]
    urgency_level: int  # 1-5 scale
    quality_requirements: int  # 1-5 scale
    budget_constraints: Optional[float] = None
    data_sensitivity: int  # 1-5 scale
    geographical_requirements: Optional[List[str]] = None
    

@dataclass
class ModelScore:
    """
    Scoring result for a model's suitability for a process.
    """
    
    model: ModelEntity
    total_score: float
    capability_score: float
    quality_score: float
    constraint_score: float
    explanation: str


class ProcessMapper:
    """
    BFO-based process mapping and model selection system.
    """
    
    def __init__(self):
        self.models: Dict[str, ModelEntity] = {}
        self.process_requirements: Dict[ProcessType, ProcessRequirements] = {}
        self._initialize_default_mappings()
    
    def _initialize_default_mappings(self):
        """Initialize default process requirements and model configurations."""
        
        # Define process requirements
        self.process_requirements.update({
            ProcessType.TRUTH_SEEKING_ANALYSIS: ProcessRequirements(
                required_capabilities=[ModelCapability.TRUTH_SEEKING, ModelCapability.SCIENTIFIC_REASONING],
                minimum_intelligence=65,
                intelligence_weight=0.5,
                safety_weight=0.3
            ),
            
            ProcessType.ETHICAL_ANALYSIS: ProcessRequirements(
                required_capabilities=[ModelCapability.ETHICAL_REASONING, ModelCapability.CONSTITUTIONAL_AI],
                minimum_intelligence=60,
                intelligence_weight=0.3,
                safety_weight=0.5
            ),
            
            ProcessType.CODE_GENERATION: ProcessRequirements(
                required_capabilities=[ModelCapability.CODE_GENERATION, ModelCapability.TECHNICAL_ANALYSIS],
                minimum_intelligence=55,
                intelligence_weight=0.4,
                speed_weight=0.3
            ),
            
            ProcessType.IMAGE_GENERATION: ProcessRequirements(
                required_capabilities=[ModelCapability.IMAGE_GENERATION, ModelCapability.MULTIMODAL_PROCESSING],
                minimum_intelligence=40,
                intelligence_weight=0.2,
                speed_weight=0.4
            ),
            
            ProcessType.REAL_TIME_SEARCH: ProcessRequirements(
                required_capabilities=[ModelCapability.REAL_TIME_SEARCH, ModelCapability.WEB_BROWSING],
                minimum_intelligence=50,
                require_real_time=True,
                speed_weight=0.4,
                intelligence_weight=0.3
            ),
            
            ProcessType.DOCUMENT_ANALYSIS: ProcessRequirements(
                required_capabilities=[ModelCapability.DOCUMENT_PROCESSING],
                minimum_intelligence=45,
                minimum_context_window=100000,  # 100K tokens minimum
                intelligence_weight=0.3,
                cost_weight=0.4  # Important for long documents
            ),
            
            ProcessType.INSTRUCTION_FOLLOWING: ProcessRequirements(
                required_capabilities=[ModelCapability.INSTRUCTION_FOLLOWING],
                minimum_intelligence=40,
                intelligence_weight=0.3,
                reliability_weight=0.3,
                cost_weight=0.4
            )
        })
        
        # Initialize model entities (will be populated from actual model configurations)
        self._initialize_model_entities()
    
    def _initialize_model_entities(self):
        """Initialize model entities with their BFO properties."""
        
        # Grok (xAI) - Truth-seeking supremacy
        self.models["grok"] = ModelEntity(
            name="Grok",
            provider="xAI",
            model_id="grok-4-latest",
            api_endpoint="https://api.x.ai/v1/",
            qualities=ModelQualities(
                intelligence_score=73,
                speed_tokens_per_sec=200.0,  # Estimated
                cost_per_million_tokens=6.00,
                context_window_tokens=1000000,
                latency_first_token_ms=500.0,
                reliability_uptime_percent=99.0,
                safety_rating=8
            ),
            capabilities=[
                ModelCapability.TRUTH_SEEKING,
                ModelCapability.SCIENTIFIC_REASONING,
                ModelCapability.REAL_TIME_SEARCH,
                ModelCapability.LOGICAL_REASONING
            ],
            specializations=[
                ProcessType.TRUTH_SEEKING_ANALYSIS,
                ProcessType.LOGICAL_REASONING,
                ProcessType.SCIENTIFIC_REASONING
            ],
            deployment_regions=["us-east", "us-west", "eu-west"],
            availability_hours="24/7",
            data_sovereignty="us"
        )
        
        # GPT-4o (OpenAI) - General excellence
        self.models["gpt4o"] = ModelEntity(
            name="GPT-4o",
            provider="OpenAI",
            model_id="gpt-4o",
            api_endpoint="https://api.openai.com/v1/",
            qualities=ModelQualities(
                intelligence_score=71,
                speed_tokens_per_sec=125.9,
                cost_per_million_tokens=3.50,
                context_window_tokens=1000000,
                latency_first_token_ms=450.0,
                reliability_uptime_percent=99.5,
                safety_rating=9
            ),
            capabilities=[
                ModelCapability.REAL_TIME_SEARCH,
                ModelCapability.TECHNICAL_ANALYSIS,
                ModelCapability.CREATIVE_WRITING,
                ModelCapability.MULTIMODAL_PROCESSING
            ],
            specializations=[
                ProcessType.MARKET_ANALYSIS,
                ProcessType.STRATEGIC_PLANNING,
                ProcessType.CREATIVE_WRITING
            ],
            deployment_regions=["global"],
            availability_hours="24/7",
            data_sovereignty="us"
        )
        
        # Gemini (Google) - Multimodal speed leader
        self.models["gemini"] = ModelEntity(
            name="Gemini",
            provider="Google",
            model_id="gemini-2.5-pro",
            api_endpoint="https://generativelanguage.googleapis.com/",
            qualities=ModelQualities(
                intelligence_score=70,
                speed_tokens_per_sec=646.0,  # Flash-Lite champion
                cost_per_million_tokens=3.44,
                context_window_tokens=10000000,  # 10M tokens
                latency_first_token_ms=290.0,
                reliability_uptime_percent=99.8,
                safety_rating=9
            ),
            capabilities=[
                ModelCapability.IMAGE_GENERATION,
                ModelCapability.MULTIMODAL_PROCESSING,
                ModelCapability.REAL_TIME_SEARCH,
                ModelCapability.DOCUMENT_PROCESSING
            ],
            specializations=[
                ProcessType.IMAGE_GENERATION,
                ProcessType.MULTIMODAL_ANALYSIS,
                ProcessType.DOCUMENT_ANALYSIS
            ],
            deployment_regions=["global"],
            availability_hours="24/7",
            data_sovereignty="global"
        )
        
        # Claude (Anthropic) - Ethical reasoning
        self.models["claude"] = ModelEntity(
            name="Claude",
            provider="Anthropic",
            model_id="claude-3-5-sonnet",
            api_endpoint="https://api.anthropic.com/",
            qualities=ModelQualities(
                intelligence_score=64,
                speed_tokens_per_sec=86.9,
                cost_per_million_tokens=30.00,
                context_window_tokens=200000,
                latency_first_token_ms=1140.0,
                reliability_uptime_percent=99.2,
                safety_rating=10  # Best safety rating
            ),
            capabilities=[
                ModelCapability.ETHICAL_REASONING,
                ModelCapability.CONSTITUTIONAL_AI,
                ModelCapability.CREATIVE_WRITING,
                ModelCapability.TECHNICAL_ANALYSIS
            ],
            specializations=[
                ProcessType.ETHICAL_ANALYSIS,
                ProcessType.EXECUTIVE_COMMUNICATION,
                ProcessType.RESEARCH_SYNTHESIS
            ],
            deployment_regions=["us-east", "us-west"],
            availability_hours="24/7",
            data_sovereignty="us"
        )
        
        # Mistral (Mistral AI) - Code and math specialist
        self.models["mistral"] = ModelEntity(
            name="Mistral",
            provider="Mistral AI",
            model_id="mistral-large-2",
            api_endpoint="https://api.mistral.ai/",
            qualities=ModelQualities(
                intelligence_score=56,
                speed_tokens_per_sec=198.3,
                cost_per_million_tokens=2.75,
                context_window_tokens=128000,
                latency_first_token_ms=300.0,
                reliability_uptime_percent=99.0,
                safety_rating=8
            ),
            capabilities=[
                ModelCapability.CODE_GENERATION,
                ModelCapability.MATHEMATICAL_REASONING,
                ModelCapability.TECHNICAL_ANALYSIS,
                ModelCapability.MULTILINGUAL_SUPPORT
            ],
            specializations=[
                ProcessType.CODE_GENERATION,
                ProcessType.MATHEMATICAL_COMPUTATION,
                ProcessType.SYSTEM_DESIGN,
                ProcessType.DEBUGGING
            ],
            deployment_regions=["eu-west", "us-east"],
            availability_hours="24/7",
            data_sovereignty="eu"
        )
        
        # Llama (Meta) - Value and context champion
        self.models["llama"] = ModelEntity(
            name="Llama",
            provider="Meta",
            model_id="llama-4-scout",
            api_endpoint="https://api.meta.ai/",
            qualities=ModelQualities(
                intelligence_score=43,
                speed_tokens_per_sec=175.3,
                cost_per_million_tokens=0.23,  # Best value
                context_window_tokens=10000000,  # 10M tokens
                latency_first_token_ms=320.0,
                reliability_uptime_percent=99.0,
                safety_rating=8
            ),
            capabilities=[
                ModelCapability.INSTRUCTION_FOLLOWING,
                ModelCapability.DOCUMENT_PROCESSING,
                ModelCapability.CREATIVE_WRITING,
                ModelCapability.CONVERSATION_MANAGEMENT
            ],
            specializations=[
                ProcessType.INSTRUCTION_FOLLOWING,
                ProcessType.CONVERSATION_MANAGEMENT,
                ProcessType.DOCUMENT_ANALYSIS
            ],
            deployment_regions=["global"],
            availability_hours="24/7",
            data_sovereignty="global"
        )
    
    def map_process_to_models(
        self,
        process_type: ProcessType,
        context: Optional[ProcessContext] = None
    ) -> List[ModelScore]:
        """
        Map a process to suitable models using BFO-based scoring.
        
        Returns list of models sorted by suitability score (highest first).
        """
        
        if process_type not in self.process_requirements:
            raise ValueError(f"Unknown process type: {process_type}")
        
        requirements = self.process_requirements[process_type]
        scores = []
        
        for model in self.models.values():
            score = self._score_model_for_process(model, requirements, context)
            if score.total_score > 0:  # Only include viable models
                scores.append(score)
        
        # Sort by total score (highest first)
        scores.sort(key=lambda x: x.total_score, reverse=True)
        return scores
    
    def _score_model_for_process(
        self,
        model: ModelEntity,
        requirements: ProcessRequirements,
        context: Optional[ProcessContext] = None
    ) -> ModelScore:
        """Score a model's suitability for a process."""
        
        # Check hard constraints first
        if not self._meets_hard_constraints(model, requirements):
            return ModelScore(
                model=model,
                total_score=0.0,
                capability_score=0.0,
                quality_score=0.0,
                constraint_score=0.0,
                explanation="Failed hard constraints"
            )
        
        # Calculate capability score
        capability_score = self._calculate_capability_score(model, requirements)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(model, requirements)
        
        # Calculate context score
        constraint_score = self._calculate_constraint_score(model, requirements, context)
        
        # Weighted total score
        total_score = (
            capability_score * 0.4 +
            quality_score * 0.4 +
            constraint_score * 0.2
        )
        
        explanation = f"Capability: {capability_score:.2f}, Quality: {quality_score:.2f}, Constraints: {constraint_score:.2f}"
        
        return ModelScore(
            model=model,
            total_score=total_score,
            capability_score=capability_score,
            quality_score=quality_score,
            constraint_score=constraint_score,
            explanation=explanation
        )
    
    def _meets_hard_constraints(self, model: ModelEntity, requirements: ProcessRequirements) -> bool:
        """Check if model meets hard constraints."""
        
        # Check required capabilities
        for capability in requirements.required_capabilities:
            if capability not in model.capabilities:
                return False
        
        # Check minimum intelligence
        if model.qualities.intelligence_score < requirements.minimum_intelligence:
            return False
        
        # Check maximum cost
        if (requirements.maximum_cost_per_token and 
            model.qualities.cost_per_million_tokens > requirements.maximum_cost_per_token):
            return False
        
        # Check minimum context window
        if (requirements.minimum_context_window and 
            model.qualities.context_window_tokens < requirements.minimum_context_window):
            return False
        
        # Check maximum latency
        if (requirements.maximum_latency_ms and 
            model.qualities.latency_first_token_ms > requirements.maximum_latency_ms):
            return False
        
        return True
    
    def _calculate_capability_score(self, model: ModelEntity, requirements: ProcessRequirements) -> float:
        """Calculate capability match score (0-1)."""
        
        required_caps = set(requirements.required_capabilities)
        model_caps = set(model.capabilities)
        
        if not required_caps:
            return 1.0
        
        # Percentage of required capabilities that the model has
        intersection = len(required_caps.intersection(model_caps))
        return intersection / len(required_caps)
    
    def _calculate_quality_score(self, model: ModelEntity, requirements: ProcessRequirements) -> float:
        """Calculate quality score based on weighted requirements (0-1)."""
        
        qualities = model.qualities
        
        # Normalize scores to 0-1 scale
        intelligence_norm = min(qualities.intelligence_score / 100.0, 1.0)
        speed_norm = min(qualities.speed_tokens_per_sec / 1000.0, 1.0)  # Assume 1000 t/s is perfect
        cost_norm = max(0, 1.0 - qualities.cost_per_million_tokens / 50.0)  # Assume $50/1M is worst
        reliability_norm = qualities.reliability_uptime_percent / 100.0
        safety_norm = qualities.safety_rating / 10.0
        
        # Weighted combination
        score = (
            intelligence_norm * requirements.intelligence_weight +
            speed_norm * requirements.speed_weight +
            cost_norm * requirements.cost_weight +
            reliability_norm * requirements.reliability_weight +
            safety_norm * requirements.safety_weight
        )
        
        return min(score, 1.0)
    
    def _calculate_constraint_score(
        self, 
        model: ModelEntity, 
        requirements: ProcessRequirements,
        context: Optional[ProcessContext] = None
    ) -> float:
        """Calculate constraint satisfaction score (0-1)."""
        
        if not context:
            return 1.0
        
        score = 1.0
        
        # Data sovereignty preference
        if context.geographical_requirements:
            if model.data_sovereignty not in context.geographical_requirements:
                score *= 0.5
        
        # Budget constraints
        if context.budget_constraints:
            if model.qualities.cost_per_million_tokens > context.budget_constraints:
                score *= 0.3
        
        # Data sensitivity (prefer higher safety ratings for sensitive data)
        if context.data_sensitivity >= 4:
            score *= (model.qualities.safety_rating / 10.0)
        
        return score
    
    def get_optimal_model(
        self,
        process_type: ProcessType,
        context: Optional[ProcessContext] = None
    ) -> Optional[ModelEntity]:
        """Get the optimal model for a process."""
        
        scored_models = self.map_process_to_models(process_type, context)
        return scored_models[0].model if scored_models else None
    
    def get_fallback_models(
        self,
        process_type: ProcessType,
        primary_model: str,
        context: Optional[ProcessContext] = None
    ) -> List[ModelEntity]:
        """Get fallback models excluding the primary model."""
        
        scored_models = self.map_process_to_models(process_type, context)
        return [
            score.model for score in scored_models 
            if score.model.name.lower() != primary_model.lower()
        ]


# Global process mapper instance
process_mapper = ProcessMapper()