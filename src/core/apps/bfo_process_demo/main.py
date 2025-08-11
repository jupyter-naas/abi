"""
BFO Process Routing Demo

This demo showcases the integration of BFO (Basic Formal Ontology) process mapping
with ABI's agent system for intelligent process-based agent selection.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'lib'))

from abi.services.process_router.ProcessRouter import ProcessRouter, ProcessType, ProcessContext
from abi.services.agent.beta.EnhancedIntentMapper import EnhancedIntentMapper, IntentMappingStrategy
from abi.services.agent.beta.IntentMapper import Intent, IntentType


def log(message: str):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def demo_bfo_process_routing():
    """Demo BFO process routing capabilities"""
    
    log("🧠 BFO Process Routing Demo")
    log("=" * 50)
    
    # Initialize Process Router
    log("📡 Initializing BFO Process Router...")
    process_router = ProcessRouter()
    
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
        process_type = process_router.map_intent_to_process(prompt)
        log(f"📝 '{prompt[:50]}...' → {process_type.value}")
    
    # Test process analytics
    log("\n📊 Process Analytics:")
    log("-" * 30)
    
    analytics = process_router.get_process_analytics()
    if analytics:
        log(f"Total executions: {analytics.get('total_executions', 0)}")
        log(f"Success rate: {analytics.get('success_rate', 0)*100:.1f}%")
        log(f"Average execution time: {analytics.get('average_execution_time_ms', 0):.0f}ms")
    else:
        log("No execution data available yet")
    
    # Test optimization suggestions
    log("\n💡 Optimization Suggestions:")
    log("-" * 30)
    
    suggestions = process_router.get_optimization_suggestions()
    if suggestions:
        for suggestion in suggestions:
            log(f"💭 {suggestion}")
    else:
        log("No optimization suggestions available")


def demo_enhanced_intent_mapping():
    """Demo enhanced intent mapping with BFO integration"""
    
    log("\n🎯 Enhanced Intent Mapping Demo")
    log("=" * 50)
    
    # Create sample intents
    sample_intents = [
        Intent("code_generation", IntentType.AGENT, "coding"),
        Intent("image_generation", IntentType.AGENT, "visual"),
        Intent("analysis", IntentType.AGENT, "research"),
        Intent("translation", IntentType.AGENT, "language"),
        Intent("calculation", IntentType.AGENT, "math")
    ]
    
    # Initialize Enhanced Intent Mapper
    log("📡 Initializing Enhanced Intent Mapper...")
    enhanced_mapper = EnhancedIntentMapper(
        intents=sample_intents,
        strategy=IntentMappingStrategy.HYBRID
    )
    
    # Test enhanced intent mapping
    test_prompts = [
        "I need to write a Python function",
        "Create a beautiful landscape image",
        "Analyze this dataset for patterns",
        "Translate this document to Spanish",
        "Calculate the ROI for this investment"
    ]
    
    log("\n🔍 Testing Enhanced Intent Mapping:")
    log("-" * 40)
    
    for prompt in test_prompts:
        results = enhanced_mapper.map_intent_enhanced(prompt, k=2)
        
        log(f"\n📝 Prompt: '{prompt}'")
        for i, result in enumerate(results, 1):
            strategy_name = result.strategy.value
            confidence = result.confidence
            intent_value = result.intent.intent_value
            process_type = result.process_type.value if result.process_type else "None"
            
            log(f"  {i}. Strategy: {strategy_name}")
            log(f"     Intent: {intent_value}")
            log(f"     Process: {process_type}")
            log(f"     Confidence: {confidence:.2f}")


def demo_process_execution():
    """Demo process execution with BFO routing"""
    
    log("\n⚡ Process Execution Demo")
    log("=" * 50)
    
    # Initialize Process Router
    process_router = ProcessRouter()
    
    # Create a mock context
    context = ProcessContext(
        user_preferences={'quality': 'high', 'speed': 'medium'},
        urgency_level=3,
        quality_requirements=4,
        budget_constraints=100.0,
        data_sensitivity=2,
        geographical_requirements=['US', 'EU']
    )
    
    # Test process execution (without actual agents)
    test_prompts = [
        "Write a function to sort a list",
        "Generate a logo for my company",
        "Analyze the sentiment of this text"
    ]
    
    log("\n🔍 Testing Process Execution (Mock):")
    log("-" * 40)
    
    for prompt in test_prompts:
        log(f"\n📝 Processing: '{prompt}'")
        
        # Map to process
        process_type = process_router.map_intent_to_process(prompt, context)
        log(f"  🎯 Mapped to: {process_type.value}")
        
        # Get optimal model (from BFO mapping)
        optimal_model = process_router.process_mapper.get_optimal_model(process_type, context)
        if optimal_model:
            log(f"  🤖 Optimal model: {optimal_model.name} ({optimal_model.provider})")
            log(f"  💰 Cost per million tokens: ${optimal_model.qualities.cost_per_million_tokens}")
            log(f"  ⚡ Speed: {optimal_model.qualities.speed_tokens_per_sec:.0f} tokens/sec")
        else:
            log("  ⚠️  No optimal model found")


def main():
    """Main demo function"""
    
    log("🚀 Starting BFO Process Routing Integration Demo")
    log("=" * 60)
    
    try:
        # Demo 1: Basic BFO Process Routing
        demo_bfo_process_routing()
        
        # Demo 2: Enhanced Intent Mapping
        demo_enhanced_intent_mapping()
        
        # Demo 3: Process Execution
        demo_process_execution()
        
        log("\n✅ Demo completed successfully!")
        log("\n🎯 Key Benefits Demonstrated:")
        log("  • Intelligent process-based agent selection")
        log("  • BFO ontological knowledge integration")
        log("  • Enhanced intent mapping with process understanding")
        log("  • Context-aware agent routing")
        log("  • Process analytics and optimization")
        
    except Exception as e:
        log(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
