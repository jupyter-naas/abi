"""
Basic BFO Process Routing Demo

A basic demo that showcases BFO process mapping without requiring
the full ProcessMapper initialization.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))

from abi.services.process_router.process_mapping import ProcessType, ProcessContext


def log(message: str):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def demo_process_classification():
    """Demo BFO process classification"""
    
    log("🧠 BFO Process Classification Demo")
    log("=" * 50)
    
    # Test process classification
    test_prompts = [
        "Write a Python script to calculate fibonacci numbers",
        "Generate an image of a sunset over mountains", 
        "Analyze the performance of this code and suggest optimizations",
        "Translate this text from English to French",
        "Search for the latest news about AI developments",
        "Calculate the compound interest on $10,000 at 5% for 10 years",
        "Summarize the key points from this research paper",
        "Create a story about a magical forest",
        "Debug this JavaScript function",
        "Design a database schema for a social media app"
    ]
    
    log("\n🔍 Testing Process Classification:")
    log("-" * 40)
    
    for prompt in test_prompts:
        # Simple keyword-based classification
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ['code', 'program', 'develop', 'script', 'python', 'javascript']):
            process_type = ProcessType.CODE_GENERATION
        elif any(word in prompt_lower for word in ['image', 'picture', 'photo', 'visual', 'generate']):
            process_type = ProcessType.IMAGE_GENERATION
        elif any(word in prompt_lower for word in ['analyze', 'examine', 'study', 'research', 'performance']):
            process_type = ProcessType.TECHNICAL_ANALYSIS
        elif any(word in prompt_lower for word in ['translate', 'language', 'french']):
            process_type = ProcessType.TRANSLATION
        elif any(word in prompt_lower for word in ['search', 'find', 'look up', 'news']):
            process_type = ProcessType.REAL_TIME_SEARCH
        elif any(word in prompt_lower for word in ['calculate', 'math', 'compute', 'interest']):
            process_type = ProcessType.MATHEMATICAL_COMPUTATION
        elif any(word in prompt_lower for word in ['summarize', 'summary', 'key points']):
            process_type = ProcessType.SUMMARIZATION
        elif any(word in prompt_lower for word in ['story', 'create', 'write', 'magical']):
            process_type = ProcessType.CREATIVE_WRITING
        elif any(word in prompt_lower for word in ['debug', 'fix', 'error']):
            process_type = ProcessType.DEBUGGING
        elif any(word in prompt_lower for word in ['design', 'schema', 'database']):
            process_type = ProcessType.SYSTEM_DESIGN
        else:
            process_type = ProcessType.PROBLEM_SOLVING
        
        log(f"📝 '{prompt[:50]}...' → {process_type.value}")


def demo_process_categories():
    """Demo BFO process categories"""
    
    log("\n📋 BFO Process Categories Demo")
    log("=" * 50)
    
    # Show all available process types
    process_categories = {
        "Analysis Processes": [
            ProcessType.TRUTH_SEEKING_ANALYSIS,
            ProcessType.ETHICAL_ANALYSIS,
            ProcessType.TECHNICAL_ANALYSIS,
            ProcessType.MARKET_ANALYSIS,
            ProcessType.DATA_ANALYSIS,
            ProcessType.DOCUMENT_ANALYSIS,
            ProcessType.MULTIMODAL_ANALYSIS
        ],
        "Creative Processes": [
            ProcessType.IMAGE_GENERATION,
            ProcessType.CREATIVE_WRITING,
            ProcessType.BRAINSTORMING,
            ProcessType.STORYTELLING,
            ProcessType.CONTENT_CREATION
        ],
        "Technical Processes": [
            ProcessType.CODE_GENERATION,
            ProcessType.MATHEMATICAL_COMPUTATION,
            ProcessType.SYSTEM_DESIGN,
            ProcessType.DEBUGGING,
            ProcessType.ALGORITHM_DEVELOPMENT
        ],
        "Information Processes": [
            ProcessType.REAL_TIME_SEARCH,
            ProcessType.RESEARCH_SYNTHESIS,
            ProcessType.TRANSLATION,
            ProcessType.SUMMARIZATION,
            ProcessType.FACT_CHECKING
        ],
        "Communication Processes": [
            ProcessType.INSTRUCTION_FOLLOWING,
            ProcessType.CONVERSATION_MANAGEMENT,
            ProcessType.EXECUTIVE_COMMUNICATION,
            ProcessType.TECHNICAL_DOCUMENTATION,
            ProcessType.CUSTOMER_SUPPORT
        ],
        "Reasoning Processes": [
            ProcessType.LOGICAL_REASONING,
            ProcessType.CAUSAL_REASONING,
            ProcessType.ANALOGICAL_REASONING,
            ProcessType.STRATEGIC_PLANNING,
            ProcessType.PROBLEM_SOLVING,
            ProcessType.SCIENTIFIC_REASONING
        ]
    }
    
    log("\n🔍 Available Process Categories:")
    log("-" * 40)
    
    for category, processes in process_categories.items():
        log(f"\n📂 {category}:")
        for process in processes:
            log(f"  • {process.value}")


def demo_context_awareness():
    """Demo context-aware process selection"""
    
    log("\n🎯 Context-Aware Process Selection Demo")
    log("=" * 50)
    
    # Create different contexts
    contexts = {
        "High Priority": ProcessContext(
            user_preferences={'quality': 'high', 'speed': 'high'},
            urgency_level=5,
            quality_requirements=5,
            budget_constraints=None,
            data_sensitivity=3,
            geographical_requirements=['US']
        ),
        "Budget Conscious": ProcessContext(
            user_preferences={'quality': 'medium', 'speed': 'medium'},
            urgency_level=2,
            quality_requirements=3,
            budget_constraints=50.0,
            data_sensitivity=1,
            geographical_requirements=['US', 'EU']
        ),
        "Privacy Focused": ProcessContext(
            user_preferences={'quality': 'high', 'speed': 'low'},
            urgency_level=1,
            quality_requirements=5,
            budget_constraints=200.0,
            data_sensitivity=5,
            geographical_requirements=['EU']
        )
    }
    
    log("\n🔍 Context Examples:")
    log("-" * 30)
    
    for context_name, context in contexts.items():
        log(f"\n📋 {context_name}:")
        log(f"  🚨 Urgency: {context.urgency_level}/5")
        log(f"  🎯 Quality: {context.quality_requirements}/5")
        log(f"  💰 Budget: ${context.budget_constraints}" if context.budget_constraints else "  💰 Budget: No limit")
        log(f"  🔒 Sensitivity: {context.data_sensitivity}/5")
        log(f"  🌍 Regions: {', '.join(context.geographical_requirements)}")


def main():
    """Main demo function"""
    
    log("🚀 Starting Basic BFO Process Routing Demo")
    log("=" * 60)
    
    try:
        # Demo 1: Process Classification
        demo_process_classification()
        
        # Demo 2: Process Categories
        demo_process_categories()
        
        # Demo 3: Context Awareness
        demo_context_awareness()
        
        log("\n✅ Demo completed successfully!")
        log("\n🎯 Key Benefits Demonstrated:")
        log("  • Intelligent process classification")
        log("  • Comprehensive BFO process categories")
        log("  • Context-aware process selection")
        log("  • Ontological knowledge integration")
        log("  • Scalable process routing framework")
        
        log("\n🔮 Next Steps:")
        log("  • Integrate with actual agent selection")
        log("  • Add process execution tracking")
        log("  • Implement analytics and optimization")
        log("  • Connect to knowledge graph for dynamic mappings")
        
    except Exception as e:
        log(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
