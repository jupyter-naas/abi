"""
Derived Process Mapping System

This module implements process-to-model mapping based on capabilities
actually extracted from model documentation, rather than predefined processes.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DerivedProcess:
    """A process derived from actual model capabilities."""
    name: str
    category: str
    complexity_level: int  # Number of supporting models
    supporting_models: List[str]
    required_capabilities: List[str]
    description: str


@dataclass 
class ProcessRoutingResult:
    """Result of process-to-model routing."""
    primary_model: str
    secondary_models: List[str]
    process_name: str
    confidence: float
    reasoning: str


class DerivedProcessMapper:
    """Maps user requests to derived processes and optimal models."""
    
    def __init__(self):
        self.processes = self._load_derived_processes()
        self.model_capabilities = self._load_model_capabilities()
        
    def _load_derived_processes(self) -> Dict[str, DerivedProcess]:
        """Load the derived processes from our capability analysis."""
        
        # These are the actual processes derived from model capabilities
        derived_processes = {
            # Information Processes (Most Universal)
            "document_analysis": DerivedProcess(
                name="Document Analysis",
                category="Information",
                complexity_level=6,
                supporting_models=["claude", "llama", "gemini", "grok", "chatgpt", "mistral"],
                required_capabilities=["document_processing", "context_handling", "text_analysis"],
                description="Analyze, comprehend, and extract insights from documents"
            ),
            
            "image_generation": DerivedProcess(
                name="Image Generation", 
                category="Information",
                complexity_level=5,
                supporting_models=["claude", "gemini", "grok", "chatgpt", "mistral"],
                required_capabilities=["image_generation", "visual_creation", "multimodal_processing"],
                description="Create, generate, and produce visual content and images"
            ),
            
            "ethical_reasoning": DerivedProcess(
                name="Ethical Reasoning",
                category="Information", 
                complexity_level=5,
                supporting_models=["claude", "gemini", "grok", "chatgpt", "mistral"],
                required_capabilities=["ethical_analysis", "constitutional_ai", "safety_assessment"],
                description="Analyze ethical implications and provide moral reasoning"
            ),
            
            "creative_writing": DerivedProcess(
                name="Creative Writing",
                category="Information",
                complexity_level=3,
                supporting_models=["llama", "claude", "gemini"],
                required_capabilities=["creative_writing", "content_creation", "storytelling"],
                description="Generate creative content, stories, and written material"
            ),
            
            "data_processing": DerivedProcess(
                name="Data Processing",
                category="Information", 
                complexity_level=3,
                supporting_models=["llama", "chatgpt", "gemini"],
                required_capabilities=["data_analysis", "processing", "computation"],
                description="Process, analyze, and manipulate data structures"
            ),
            
            "multimodal_processing": DerivedProcess(
                name="Multimodal Processing",
                category="Information",
                complexity_level=1,
                supporting_models=["gemini"],
                required_capabilities=["multimodal_processing", "cross_modal_understanding"],
                description="Process and understand multiple data modalities simultaneously"
            ),
            
            # Technical Processes
            "system_design": DerivedProcess(
                name="System Design",
                category="Technical",
                complexity_level=5,
                supporting_models=["claude", "gemini", "grok", "chatgpt", "mistral"],
                required_capabilities=["system_architecture", "design_patterns", "technical_planning"],
                description="Design and architect complex systems and solutions"
            ),
            
            "code_generation": DerivedProcess(
                name="Code Generation",
                category="Technical",
                complexity_level=4,
                supporting_models=["llama", "perplexity", "mistral", "gemini"],
                required_capabilities=["code_generation", "programming", "algorithm_development"],
                description="Generate, write, and create programming code and algorithms"
            ),
            
            "mathematical_computation": DerivedProcess(
                name="Mathematical Computation",
                category="Technical",
                complexity_level=3,
                supporting_models=["grok", "mistral", "gemini"],
                required_capabilities=["mathematical_reasoning", "computation", "numerical_analysis"],
                description="Perform mathematical calculations, reasoning, and computational tasks"
            ),
            
            # Cognitive Processes
            "scientific_reasoning": DerivedProcess(
                name="Scientific Reasoning",
                category="Cognitive",
                complexity_level=5,
                supporting_models=["claude", "gemini", "perplexity", "grok", "chatgpt"],
                required_capabilities=["scientific_analysis", "logical_reasoning", "empirical_thinking"],
                description="Apply scientific methodology and reasoning to complex problems"
            ),
            
            # Interactive Processes
            "conversation_management": DerivedProcess(
                name="Conversation Management",
                category="Interactive",
                complexity_level=4,
                supporting_models=["perplexity", "claude", "chatgpt", "llama"],
                required_capabilities=["dialogue_management", "context_retention", "turn_taking"],
                description="Manage complex conversations and dialogue interactions"
            ),
            
            # Creative Processes (Universal!)
            "real_time_search": DerivedProcess(
                name="Real-Time Search",
                category="Creative",
                complexity_level=7,  # ALL models!
                supporting_models=["claude", "llama", "gemini", "perplexity", "grok", "chatgpt", "mistral"],
                required_capabilities=["web_search", "real_time_data", "information_retrieval"],
                description="Search for and retrieve current, real-time information from various sources"
            ),
            
            # Analytical Processes
            "risk_assessment": DerivedProcess(
                name="Risk Assessment",
                category="Analytical",
                complexity_level=1,
                supporting_models=["claude"],
                required_capabilities=["risk_analysis", "safety_evaluation", "compliance_checking"],
                description="Assess and analyze potential risks and safety concerns"
            ),
            
            # Communication Processes
            "instruction_following": DerivedProcess(
                name="Instruction Following",
                category="Communication",
                complexity_level=2,
                supporting_models=["mistral", "llama"],
                required_capabilities=["task_completion", "instruction_parsing", "adaptive_assistance"],
                description="Follow complex instructions and complete specified tasks"
            ),
            
            # Specialized Processes (Model-Specific)
            "truth_seeking_analysis": DerivedProcess(
                name="Truth-Seeking Analysis",
                category="Specialized",
                complexity_level=1,
                supporting_models=["grok"],
                required_capabilities=["truth_seeking", "contrarian_analysis", "fact_verification"],
                description="Pursue truth through contrarian analysis and fact-seeking (Grok exclusive)"
            ),
            
            "constitutional_ai_compliance": DerivedProcess(
                name="Constitutional AI Compliance",
                category="Specialized", 
                complexity_level=1,
                supporting_models=["claude"],
                required_capabilities=["constitutional_ai", "ethical_compliance", "safety_filtering"],
                description="Apply Constitutional AI principles for ethical compliance (Claude exclusive)"
            ),
            
            "european_data_sovereignty": DerivedProcess(
                name="European Data Sovereignty",
                category="Specialized",
                complexity_level=1,
                supporting_models=["mistral"],
                required_capabilities=["gdpr_compliance", "european_regulations", "data_localization"],
                description="Ensure European data compliance and sovereignty (Mistral exclusive)"
            ),
            
            "massive_context_processing": DerivedProcess(
                name="Massive Context Processing", 
                category="Specialized",
                complexity_level=2,
                supporting_models=["llama", "gemini"],
                required_capabilities=["large_context_windows", "long_document_processing", "memory_management"],
                description="Process extremely large contexts (10M+ tokens) for comprehensive analysis"
            )
        }
        
        return derived_processes
    
    def _load_model_capabilities(self) -> Dict[str, Dict]:
        """Load model capability profiles for routing decisions."""
        
        return {
            "grok": {
                "intelligence": 73,
                "speed": 200,
                "cost": 6.00,
                "specializations": ["truth_seeking", "scientific_reasoning", "contrarian_analysis"],
                "unique_capabilities": ["highest_intelligence", "truth_seeking", "x_platform_integration"]
            },
            "chatgpt": {
                "intelligence": 71, 
                "speed": 125.9,
                "cost": 3.50,
                "specializations": ["general_intelligence", "web_search", "research_synthesis"],
                "unique_capabilities": ["mature_ecosystem", "real_time_search", "broad_capabilities"]
            },
            "gemini": {
                "intelligence": 70,
                "speed": 646,  # Fastest globally
                "cost": 3.44,
                "specializations": ["multimodal_processing", "image_generation", "speed_optimization"],
                "unique_capabilities": ["native_image_generation", "fastest_speed", "massive_context"]
            },
            "claude": {
                "intelligence": 64,
                "speed": 86.9,
                "cost": 30.00,
                "specializations": ["ethical_reasoning", "safety_analysis", "regulatory_compliance"],
                "unique_capabilities": ["constitutional_ai", "safety_focus", "ethical_excellence"]
            },
            "mistral": {
                "intelligence": 56,
                "speed": 198.3,
                "cost": 2.75,
                "specializations": ["code_generation", "mathematical_computation", "european_compliance"],
                "unique_capabilities": ["technical_precision", "european_sovereignty", "moe_architecture"]
            },
            "llama": {
                "intelligence": 43,
                "speed": 175.3,
                "cost": 0.23,  # Best value
                "specializations": ["instruction_following", "conversation_management", "value_optimization"],
                "unique_capabilities": ["best_value", "massive_context", "open_source", "democratic_access"]
            },
            "perplexity": {
                "intelligence": 54,
                "speed": 180,  # Estimated
                "cost": 1.00,  # Estimated
                "specializations": ["real_time_search", "web_analysis", "information_retrieval"],
                "unique_capabilities": ["search_specialization", "current_information", "source_citation"]
            }
        }
    
    def route_user_request(self, user_request: str) -> ProcessRoutingResult:
        """Route a user request to the optimal process and model."""
        
        # Identify the most relevant process
        relevant_process = self._identify_process_from_request(user_request)
        
        if not relevant_process:
            # Default to general intelligence if no specific process identified
            return ProcessRoutingResult(
                primary_model="chatgpt",
                secondary_models=["grok", "gemini"],
                process_name="general_intelligence",
                confidence=0.5,
                reasoning="No specific process identified, using general intelligence model"
            )
        
        # Get optimal model for this process
        primary_model, secondary_models, confidence, reasoning = self._select_optimal_model(
            relevant_process, user_request
        )
        
        return ProcessRoutingResult(
            primary_model=primary_model,
            secondary_models=secondary_models,
            process_name=relevant_process.name,
            confidence=confidence,
            reasoning=reasoning
        )
    
    def _identify_process_from_request(self, user_request: str) -> Optional[DerivedProcess]:
        """Identify which derived process best matches the user request."""
        
        request_lower = user_request.lower()
        
        # Define process identification keywords based on actual derived processes
        process_keywords = {
            "document_analysis": ["document", "analyze", "read", "comprehend", "extract", "pdf", "text analysis"],
            "image_generation": ["image", "picture", "visual", "generate", "create image", "draw", "illustration"],
            "ethical_reasoning": ["ethical", "moral", "ethics", "right", "wrong", "should", "constitutional"],
            "creative_writing": ["write", "story", "creative", "content", "narrative", "poem", "fiction"],
            "data_processing": ["data", "process", "analyze data", "statistics", "dataset", "csv"],
            "multimodal_processing": ["multimodal", "multi-modal", "cross-modal", "image and text"],
            "system_design": ["design", "architecture", "system", "plan", "blueprint", "structure"],
            "code_generation": ["code", "program", "function", "algorithm", "implement", "programming"],
            "mathematical_computation": ["math", "calculate", "equation", "computation", "numerical", "formula"],
            "scientific_reasoning": ["scientific", "research", "hypothesis", "evidence", "experiment", "analysis"],
            "conversation_management": ["chat", "conversation", "dialogue", "discuss", "talk"],
            "real_time_search": ["search", "find", "current", "latest", "recent", "news", "web"],
            "risk_assessment": ["risk", "assess", "safety", "danger", "evaluate risk", "compliance"],
            "instruction_following": ["follow", "instructions", "task", "complete", "do this", "step by step"],
            "truth_seeking_analysis": ["truth", "fact", "verify", "contrarian", "challenge", "assumptions"],
            "constitutional_ai_compliance": ["constitutional", "safe", "compliant", "regulatory", "ethical ai"],
            "european_data_sovereignty": ["gdpr", "european", "privacy", "data protection", "eu compliance"],
            "massive_context_processing": ["long document", "book", "large context", "entire", "comprehensive"]
        }
        
        # Score each process based on keyword matches
        process_scores = {}
        for process_name, keywords in process_keywords.items():
            score = sum(1 for keyword in keywords if keyword in request_lower)
            if score > 0:
                process_scores[process_name] = score
        
        if not process_scores:
            return None
        
        # Return the highest scoring process
        best_process_name = max(process_scores, key=lambda x: process_scores[x])
        return self.processes.get(best_process_name)
    
    def _select_optimal_model(self, process: DerivedProcess, user_request: str) -> Tuple[str, List[str], float, str]:
        """Select the optimal model for a given process and request context."""
        
        supporting_models = process.supporting_models
        
        if not supporting_models:
            return "chatgpt", ["grok", "gemini"], 0.3, "No supporting models found, using default"
        
        # If only one model supports this process, it's the obvious choice
        if len(supporting_models) == 1:
            return supporting_models[0], [], 1.0, f"Exclusive capability: only {supporting_models[0]} supports {process.name}"
        
        # For multiple models, select based on context and model qualities
        request_lower = user_request.lower()
        
        # Context-based routing
        if any(word in request_lower for word in ["fast", "quick", "speed", "urgent"]):
            # Prioritize speed
            speed_ranking = {"gemini": 646, "mistral": 198.3, "grok": 200, "llama": 175.3, "chatgpt": 125.9, "claude": 86.9, "perplexity": 180}
            speed_models = [m for m in supporting_models if m in speed_ranking]
            if speed_models:
                best_model = max(speed_models, key=lambda x: speed_ranking.get(x, 0))
                others = [m for m in supporting_models if m != best_model][:2]
                return best_model, others, 0.9, f"Speed-optimized: {best_model} selected for fastest processing"
        
        if any(word in request_lower for word in ["cheap", "cost", "budget", "economical"]):
            # Prioritize cost efficiency
            cost_ranking = {"llama": 0.23, "mistral": 2.75, "gemini": 3.44, "chatgpt": 3.50, "grok": 6.00, "claude": 30.00, "perplexity": 1.00}
            cost_models = [m for m in supporting_models if m in cost_ranking]
            if cost_models:
                best_model = min(cost_models, key=lambda x: cost_ranking.get(x, 100))
                others = [m for m in supporting_models if m != best_model][:2]
                return best_model, others, 0.9, f"Cost-optimized: {best_model} selected for best value"
        
        if any(word in request_lower for word in ["smart", "intelligent", "complex", "advanced"]):
            # Prioritize intelligence
            intelligence_ranking = {"grok": 73, "chatgpt": 71, "gemini": 70, "claude": 64, "mistral": 56, "perplexity": 54, "llama": 43}
            intelligence_models = [m for m in supporting_models if m in intelligence_ranking]
            if intelligence_models:
                best_model = max(intelligence_models, key=lambda x: intelligence_ranking.get(x, 0))
                others = [m for m in supporting_models if m != best_model][:2]
                return best_model, others, 0.9, f"Intelligence-optimized: {best_model} selected for highest capability"
        
        if any(word in request_lower for word in ["safe", "ethical", "compliant", "regulatory"]):
            # Prioritize safety
            if "claude" in supporting_models:
                others = [m for m in supporting_models if m != "claude"][:2]
                return "claude", others, 0.95, "Safety-optimized: Claude selected for ethical reasoning and compliance"
        
        if any(word in request_lower for word in ["truth", "fact", "verify", "contrarian"]):
            # Prioritize truth-seeking
            if "grok" in supporting_models:
                others = [m for m in supporting_models if m != "grok"][:2]
                return "grok", others, 0.95, "Truth-seeking optimized: Grok selected for factual analysis"
        
        if any(word in request_lower for word in ["image", "visual", "picture", "multimodal"]):
            # Prioritize multimodal capabilities
            if "gemini" in supporting_models:
                others = [m for m in supporting_models if m != "gemini"][:2]
                return "gemini", others, 0.95, "Multimodal-optimized: Gemini selected for image/visual processing"
        
        if any(word in request_lower for word in ["code", "programming", "algorithm", "technical"]):
            # Prioritize technical capabilities
            if "mistral" in supporting_models:
                others = [m for m in supporting_models if m != "mistral"][:2]
                return "mistral", others, 0.9, "Technical-optimized: Mistral selected for code generation"
        
        # Default: select by intelligence + cost balance
        intelligence_ranking = {"grok": 73, "chatgpt": 71, "gemini": 70, "claude": 64, "mistral": 56, "perplexity": 54, "llama": 43}
        cost_ranking = {"llama": 0.23, "mistral": 2.75, "gemini": 3.44, "chatgpt": 3.50, "grok": 6.00, "claude": 30.00, "perplexity": 1.00}
        
        # Calculate value score (intelligence/cost ratio)
        value_scores = {}
        for model in supporting_models:
            intelligence = intelligence_ranking.get(model, 50)
            cost = cost_ranking.get(model, 10)
            value_scores[model] = intelligence / cost
        
        best_model = max(value_scores, key=lambda x: value_scores[x])
        others = [m for m in supporting_models if m != best_model][:2]
        
        return best_model, others, 0.8, f"Value-optimized: {best_model} selected for best intelligence/cost ratio"
    
    def get_process_capabilities(self) -> Dict[str, Dict]:
        """Get a summary of all derived processes and their supporting models."""
        
        summary = {}
        for process_name, process in self.processes.items():
            summary[process_name] = {
                "name": process.name,
                "category": process.category,
                "complexity": process.complexity_level,
                "models": process.supporting_models,
                "description": process.description,
                "exclusivity": "Exclusive" if process.complexity_level == 1 else "Shared"
            }
        
        return summary
    
    def explain_routing_decision(self, user_request: str) -> str:
        """Provide a detailed explanation of how a request would be routed."""
        
        result = self.route_user_request(user_request)
        
        explanation = f"""
🎯 **Process Routing Analysis**

**User Request**: "{user_request}"

**Identified Process**: {result.process_name}
**Primary Model**: {result.primary_model.upper()}
**Secondary Models**: {', '.join(result.secondary_models)}
**Confidence**: {result.confidence:.1%}

**Reasoning**: {result.reasoning}

**Process Details**:
- **Category**: {self.processes.get(result.process_name.lower().replace(' ', '_'), {}).category}
- **Complexity**: {self.processes.get(result.process_name.lower().replace(' ', '_'), {}).complexity_level} models support this
- **Supporting Models**: {', '.join(self.processes.get(result.process_name.lower().replace(' ', '_'), {}).supporting_models)}

**Model Capabilities**:
"""
        
        model_info = self.model_capabilities.get(result.primary_model, {})
        explanation += f"- **{result.primary_model.upper()}**: Intelligence {model_info.get('intelligence', 'N/A')}, Speed {model_info.get('speed', 'N/A')} t/s, Cost ${model_info.get('cost', 'N/A')}/1M"
        
        return explanation


# Global derived process mapper instance
derived_process_mapper = DerivedProcessMapper()


if __name__ == "__main__":
    # Test the derived process mapping
    mapper = DerivedProcessMapper()
    
    test_requests = [
        "Generate an image of a sunset over mountains",
        "Analyze this 50-page legal document for compliance issues", 
        "Write Python code to implement a binary search algorithm",
        "What are the ethical implications of AI in healthcare?",
        "Search for the latest news about climate change",
        "I need the fastest possible analysis of market trends",
        "Create a detailed system architecture for a microservices platform",
        "Verify the truth behind these controversial claims"
    ]
    
    print("🧠 DERIVED PROCESS MAPPING TEST\n")
    
    for request in test_requests:
        result = mapper.route_user_request(request)
        print(f"Request: {request}")
        print(f"→ Process: {result.process_name}")
        print(f"→ Primary: {result.primary_model.upper()}")
        print(f"→ Reasoning: {result.reasoning}")
        print()
    
    print("\n📊 PROCESS CAPABILITY SUMMARY:")
    capabilities = mapper.get_process_capabilities()
    for process_name, info in capabilities.items():
        models_count = len(info['models'])
        exclusivity = "🔒 EXCLUSIVE" if info['exclusivity'] == "Exclusive" else f"🤝 SHARED ({models_count} models)"
        print(f"• {info['name']}: {exclusivity} - {info['category']}")