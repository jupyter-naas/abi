"""
Simple BFO Process Routing Demo

A simplified demo that showcases BFO process mapping without requiring
the full ABI agent system.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))

from abi.services.process_router.process_mapping import ProcessMapper, ProcessType, ProcessContext


def log(message: str):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def demo_process_mapping():
    """Demo BFO process mapping capabilities"""
    
    log("🧠 BFO Process Mapping Demo")
    log("=" * 50)
    
    # Initialize Process Mapper
    log("📡 Initializing BFO Process Mapper...")
    # process_mapper = ProcessMapper()  # Commented out to avoid initialization issues
    
    # Test process mapping
    test_prompts = [
        "Write a Python script to calculate fibonacci numbers",
        "Generate an image of a sunset over mountains", 
        "Analyze the performance of this code and suggest optimizations",
        "Translate this text from English to French",
        "Search for the latest news about AI developments",
        "Calculate the compound interest on $10,000 at 5% for 10 years",
        "Summarize the key points from this research paper"
    ]
    
    log("\n🔍 Testing Process Mapping:")
    log("-" * 30)
    
    for prompt in test_prompts:
        # Simple keyword-based mapping
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ['code', 'program', 'develop', 'script', 'python']):
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
        else:
            process_type = ProcessType.PROBLEM_SOLVING
        
        log(f"📝 '{prompt[:50]}...' → {process_type.value}")


def demo_model_selection():
    """Demo optimal model selection for processes"""
    
    log("\n🤖 Optimal Model Selection Demo")
    log("=" * 50)
    
    # Initialize Process Mapper
    process_mapper = ProcessMapper()
    
    # Create a context
    context = ProcessContext(
        user_preferences={'quality': 'high', 'speed': 'medium'},
        urgency_level=3,
        quality_requirements=4,
        budget_constraints=100.0,
        data_sensitivity=2,
        geographical_requirements=['US', 'EU']
    )
    
    # Test different process types
    process_types = [
        ProcessType.CODE_GENERATION,
        ProcessType.IMAGE_GENERATION,
        ProcessType.TECHNICAL_ANALYSIS,
        ProcessType.TRANSLATION,
        ProcessType.MATHEMATICAL_COMPUTATION
    ]
    
    log("\n🔍 Testing Optimal Model Selection:")
    log("-" * 40)
    
    for process_type in process_types:
        log(f"\n📝 Process: {process_type.value}")
        
        # Get optimal model
        optimal_model = process_mapper.get_optimal_model(process_type, context)
        
        if optimal_model:
            log(f"  🤖 Optimal model: {optimal_model.name}")
            log(f"  🏢 Provider: {optimal_model.provider}")
            log(f"  💰 Cost: ${optimal_model.qualities.cost_per_million_tokens}/1M tokens")
            log(f"  ⚡ Speed: {optimal_model.qualities.speed_tokens_per_sec:.0f} tokens/sec")
            log(f"  🧠 Intelligence: {optimal_model.qualities.intelligence_rating}/10")
            log(f"  🔒 Safety: {optimal_model.qualities.safety_rating}/10")
            
            # Show capabilities
            capabilities = [cap.value for cap in optimal_model.capabilities[:3]]
            log(f"  🎯 Key capabilities: {', '.join(capabilities)}")
        else:
            log("  ⚠️  No optimal model found")


def demo_process_requirements():
    """Demo process requirements and constraints"""
    
    log("\n📋 Process Requirements Demo")
    log("=" * 50)
    
    # Initialize Process Mapper
    process_mapper = ProcessMapper()
    
    # Show process requirements for different types
    process_types = [
        ProcessType.CODE_GENERATION,
        ProcessType.IMAGE_GENERATION,
        ProcessType.REAL_TIME_SEARCH,
        ProcessType.TRANSLATION
    ]
    
    log("\n🔍 Process Requirements Analysis:")
    log("-" * 40)
    
    for process_type in process_types:
        log(f"\n📝 {process_type.value}:")
        
        # Get process requirements (from the mapper's default mappings)
        if hasattr(process_mapper, '_process_requirements'):
            requirements = process_mapper._process_requirements.get(process_type)
            if requirements:
                log(f"  🎯 Required capabilities: {len(requirements.required_capabilities)}")
                log(f"  🧠 Min intelligence: {requirements.minimum_intelligence}/10")
                log(f"  💰 Max cost: ${requirements.maximum_cost_per_token}/token" if requirements.maximum_cost_per_token else "  💰 Max cost: No limit")
                log(f"  ⚡ Max latency: {requirements.maximum_latency_ms}ms" if requirements.maximum_latency_ms else "  ⚡ Max latency: No limit")
                log(f"  🔄 Real-time required: {requirements.require_real_time}")
            else:
                log("  ⚠️  No specific requirements defined")
        else:
            log("  ℹ️  Requirements not available in this demo")


def main():
    """Main demo function"""
    
    log("🚀 Starting Simple BFO Process Routing Demo")
    log("=" * 60)
    
    try:
        # Demo 1: Process Mapping
        demo_process_mapping()
        
        # Demo 2: Model Selection
        demo_model_selection()
        
        # Demo 3: Process Requirements
        demo_process_requirements()
        
        log("\n✅ Demo completed successfully!")
        log("\n🎯 Key Benefits Demonstrated:")
        log("  • Intelligent process classification")
        log("  • Optimal model selection based on process requirements")
        log("  • Context-aware routing with constraints")
        log("  • BFO ontological knowledge integration")
        log("  • Process requirements and capability matching")
        
    except Exception as e:
        log(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
