"""
Granular Process Export System for BFO Mapping

Generates detailed Excel spreadsheet showing processes at:
- Individual AI model implementation level
- Specific tool/workflow capability level  
- BFO 7 buckets mapping for each granular process
"""

import csv
from typing import List, Dict, Any
from datetime import datetime



class GranularBFOExporter:
    """Exports granular model-level and tool-level processes with BFO mapping."""
    
    def __init__(self):
        self.model_capabilities = {
            "grok": {
                "intelligence": 73, "speed": 200, "cost": 6.00, "safety": 6,
                "unique_tools": ["real_time_search", "truth_seeking_analysis", "contrarian_reasoning"],
                "workflows": ["scientific_research", "fact_verification", "assumption_challenging"],
                "core_processes": ["truth_seeking", "real_time_info", "high_intelligence_reasoning"]
            },
            "chatgpt": {
                "intelligence": 71, "speed": 125.9, "cost": 3.50, "safety": 7,
                "unique_tools": ["web_browsing", "dall_e_integration", "code_interpreter"],
                "workflows": ["web_research", "content_creation", "general_assistance"],
                "core_processes": ["general_intelligence", "balanced_reasoning", "real_time_web"]
            },
            "gemini": {
                "intelligence": 70, "speed": 646, "cost": 3.44, "safety": 8,
                "unique_tools": ["native_image_generation", "video_processing", "multimodal_analysis"],
                "workflows": ["multimodal_processing", "creative_generation", "speed_optimization"],
                "core_processes": ["multimodal_fusion", "speed_champion", "visual_intelligence"]
            },
            "claude": {
                "intelligence": 64, "speed": 86.9, "cost": 30.00, "safety": 10,
                "unique_tools": ["constitutional_ai", "safety_filtering", "ethical_reasoning"],
                "workflows": ["ethical_analysis", "safety_assessment", "constitutional_compliance"],
                "core_processes": ["ethical_reasoning", "safety_first", "constitutional_ai"]
            },
            "mistral": {
                "intelligence": 56, "speed": 198.3, "cost": 2.75, "safety": 5,
                "unique_tools": ["code_generation", "european_compliance", "technical_analysis"],
                "workflows": ["code_development", "technical_documentation", "european_processing"],
                "core_processes": ["technical_excellence", "code_specialist", "european_sovereignty"]
            },
            "llama": {
                "intelligence": 43, "speed": 175.3, "cost": 0.23, "safety": 4,
                "unique_tools": ["massive_context", "value_processing", "open_source_tools"],
                "workflows": ["long_document_analysis", "cost_efficient_processing", "democratic_access"],
                "core_processes": ["massive_context", "value_champion", "democratic_access"]
            },
            "perplexity": {
                "intelligence": 54, "speed": 180, "cost": 1.00, "safety": 5,
                "unique_tools": ["real_time_search", "citation_generation", "source_attribution"],
                "workflows": ["research_with_sources", "fact_checking", "information_retrieval"],
                "core_processes": ["search_specialist", "source_attribution", "real_time_research"]
            }
        }
        
        # Define granular processes at model + tool + workflow level
        self.granular_processes = self._generate_granular_processes()
    
    def _generate_granular_processes(self) -> List[Dict[str, Any]]:
        """Generate granular processes for each model's capabilities, tools, and workflows."""
        
        processes = []
        process_id = 1
        
        # Model-specific core processes
        for model, data in self.model_capabilities.items():
            for core_process in data["core_processes"]:
                process = {
                    "id": f"P{process_id:03d}",
                    "name": f"{model.upper()}: {core_process.replace('_', ' ').title()}",
                    "description": f"{model.upper()}'s implementation of {core_process.replace('_', ' ')} with model-specific optimizations",
                    "type": "MODEL_CORE",
                    "model": model,
                    "category": self._categorize_process(core_process),
                    "tools": data["unique_tools"],
                    "workflows": data["workflows"],
                    "intelligence": data["intelligence"],
                    "speed": data["speed"],
                    "cost": data["cost"],
                    "safety": data["safety"],
                    "exclusivity": "EXCLUSIVE" if len([m for m in self.model_capabilities.keys() if core_process in self.model_capabilities[m]["core_processes"]]) == 1 else "SHARED"
                }
                processes.append(process)
                process_id += 1
        
        # Tool-specific processes
        all_tools = set()
        for data in self.model_capabilities.values():
            all_tools.update(data["unique_tools"])
        
        for tool in all_tools:
            supporting_models = [model for model, data in self.model_capabilities.items() if tool in data["unique_tools"]]
            avg_intelligence = sum(self.model_capabilities[m]["intelligence"] for m in supporting_models) / len(supporting_models)
            avg_speed = sum(self.model_capabilities[m]["speed"] for m in supporting_models) / len(supporting_models)
            avg_cost = sum(self.model_capabilities[m]["cost"] for m in supporting_models) / len(supporting_models)
            
            process = {
                "id": f"P{process_id:03d}",
                "name": f"TOOL: {tool.replace('_', ' ').title()}",
                "description": f"Tool capability for {tool.replace('_', ' ')} across supporting models",
                "type": "TOOL",
                "model": ", ".join(supporting_models),
                "category": "Tool",
                "tools": [tool],
                "workflows": [],
                "intelligence": avg_intelligence,
                "speed": avg_speed,
                "cost": avg_cost,
                "safety": sum(self.model_capabilities[m]["safety"] for m in supporting_models) / len(supporting_models),
                "exclusivity": "EXCLUSIVE" if len(supporting_models) == 1 else f"SHARED_{len(supporting_models)}"
            }
            processes.append(process)
            process_id += 1
        
        # Workflow-specific processes
        all_workflows = set()
        for data in self.model_capabilities.values():
            all_workflows.update(data["workflows"])
        
        for workflow in all_workflows:
            supporting_models = [model for model, data in self.model_capabilities.items() if workflow in data["workflows"]]
            avg_intelligence = sum(self.model_capabilities[m]["intelligence"] for m in supporting_models) / len(supporting_models)
            avg_speed = sum(self.model_capabilities[m]["speed"] for m in supporting_models) / len(supporting_models)
            avg_cost = sum(self.model_capabilities[m]["cost"] for m in supporting_models) / len(supporting_models)
            
            process = {
                "id": f"P{process_id:03d}",
                "name": f"WORKFLOW: {workflow.replace('_', ' ').title()}",
                "description": f"Multi-step workflow for {workflow.replace('_', ' ')} orchestrating multiple capabilities",
                "type": "WORKFLOW",
                "model": ", ".join(supporting_models),
                "category": "Workflow",
                "tools": [],
                "workflows": [workflow],
                "intelligence": avg_intelligence,
                "speed": avg_speed,
                "cost": avg_cost,
                "safety": sum(self.model_capabilities[m]["safety"] for m in supporting_models) / len(supporting_models),
                "exclusivity": "EXCLUSIVE" if len(supporting_models) == 1 else f"SHARED_{len(supporting_models)}"
            }
            processes.append(process)
            process_id += 1
        
        return processes
    
    def _categorize_process(self, process_name: str) -> str:
        """Categorize a process based on its name."""
        
        if any(word in process_name for word in ["truth", "fact", "verify", "contrarian"]):
            return "Truth-Seeking"
        elif any(word in process_name for word in ["ethical", "safety", "constitutional"]):
            return "Ethical-Safety"
        elif any(word in process_name for word in ["multimodal", "visual", "image", "video"]):
            return "Multimodal"
        elif any(word in process_name for word in ["code", "technical", "development"]):
            return "Technical"
        elif any(word in process_name for word in ["intelligence", "reasoning", "cognitive"]):
            return "Cognitive"
        elif any(word in process_name for word in ["speed", "fast", "performance"]):
            return "Performance"
        elif any(word in process_name for word in ["context", "massive", "long"]):
            return "Context"
        elif any(word in process_name for word in ["search", "real_time", "web"]):
            return "Information"
        elif any(word in process_name for word in ["value", "cost", "democratic"]):
            return "Value"
        elif any(word in process_name for word in ["european", "sovereignty", "compliance"]):
            return "Sovereignty"
        else:
            return "General"
    
    def generate_granular_excel_export(self) -> str:
        """Generate comprehensive granular Excel export as CSV file."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Granular_BFO_Process_Mapping_{timestamp}.csv"
        
        headers = [
            # Process Identification
            "Process_ID",
            "Process_Name",
            "Process_Description", 
            "Process_Type",
            "Process_Category",
            "Supporting_Model(s)",
            "Exclusivity_Level",
            "Tools_Used",
            "Workflows_Involved",
            
            # Performance Metrics
            "Intelligence_Score",
            "Speed_Tokens_Per_Sec",
            "Cost_Per_1M_Tokens",
            "Safety_Score",
            
            # BFO 7 Buckets Mapping
            "BFO_1_Material_Entities_WHAT_WHO",
            "BFO_2_Qualities_HOW_IT_IS",
            "BFO_3_Realizable_Entities_WHY_POTENTIAL", 
            "BFO_4_Processes_HOW_IT_HAPPENS",
            "BFO_5_Temporal_Regions_WHEN",
            "BFO_6_Spatial_Regions_WHERE",
            "BFO_7_Information_Entities_HOW_WE_KNOW",
            
            # Strategic Analysis
            "Competitive_Advantage",
            "Use_Case_Examples",
            "Implementation_Details",
            "Integration_Points"
        ]
        
        rows = []
        for process in self.granular_processes:
            row = self._generate_granular_process_row(process)
            rows.append(row)
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            writer.writerows(rows)
        
        print(f"📊 Granular Excel export generated: {filename}")
        print(f"   - {len(rows)} granular processes mapped to BFO 7 buckets")
        print(f"   - {len(headers)} data points per process")
        
        return filename
    
    def _generate_granular_process_row(self, process: Dict[str, Any]) -> List[str]:
        """Generate a complete row for a granular process with BFO mapping."""
        
        # BFO Mapping for this specific process
        bfo_mapping = self._map_granular_process_to_bfo(process)
        
        # Strategic analysis
        competitive_advantage = self._analyze_competitive_advantage(process)
        use_cases = self._generate_specific_use_cases(process)
        implementation_details = self._describe_implementation(process)
        integration_points = self._identify_integrations(process)
        
        return [
            # Process Identification
            process["id"],
            process["name"],
            process["description"],
            process["type"],
            process["category"],
            process["model"],
            process["exclusivity"],
            ", ".join(process["tools"]) if process["tools"] else "N/A",
            ", ".join(process["workflows"]) if process["workflows"] else "N/A",
            
            # Performance Metrics
            f"{process['intelligence']:.1f}",
            f"{process['speed']:.1f}",
            f"${process['cost']:.2f}",
            f"{process['safety']:.1f}",
            
            # BFO 7 Buckets
            bfo_mapping["material_entities"],
            bfo_mapping["qualities"],
            bfo_mapping["realizable_entities"],
            bfo_mapping["processes"],
            bfo_mapping["temporal_regions"],
            bfo_mapping["spatial_regions"],
            bfo_mapping["information_entities"],
            
            # Strategic Analysis
            competitive_advantage,
            use_cases,
            implementation_details,
            integration_points
        ]
    
    def _map_granular_process_to_bfo(self, process: Dict[str, Any]) -> Dict[str, str]:
        """Map a granular process to BFO 7 buckets with specific detail."""
        
        # BFO 1: Material Entities (WHAT/WHO)
        if process["type"] == "MODEL_CORE":
            material_entities = f"AI Model: {process['model'].upper()}; Users requiring {process['name'].lower()}; Computing infrastructure; API endpoints"
        elif process["type"] == "TOOL":
            material_entities = f"Tool System: {process['name']}; Supporting Models: {process['model']}; Tool infrastructure; Integration components"
        else:  # WORKFLOW
            material_entities = f"Workflow System: {process['name']}; Orchestrating Models: {process['model']}; Workflow engine; Process coordinator"
        
        # BFO 2: Qualities (HOW-IT-IS)
        qualities = f"Intelligence: {process['intelligence']:.1f}/100; Speed: {process['speed']:.1f} t/s; Cost: ${process['cost']:.2f}/1M; Safety: {process['safety']:.1f}/10; Exclusivity: {process['exclusivity']}"
        
        # BFO 3: Realizable Entities (WHY-POTENTIAL)
        if process["type"] == "MODEL_CORE":
            realizable_entities = f"Model-specific capability for {process['category'].lower()}; Potential for optimized {process['model']} processing; Function: Specialized model execution"
        elif process["type"] == "TOOL":
            realizable_entities = f"Tool capability for {', '.join(process['tools'])}; Potential for integrated tool usage; Function: Specific tool execution"
        else:  # WORKFLOW
            realizable_entities = f"Workflow capability for {', '.join(process['workflows'])}; Potential for multi-step orchestration; Function: Complex process coordination"
        
        # BFO 4: Processes (HOW-IT-HAPPENS) - The core granular process
        processes = f"GRANULAR PROCESS: {process['name']} - {process['description']}; Execution via {process['type'].lower()} optimization; Context-aware routing to optimal implementation"
        
        # BFO 5: Temporal Regions (WHEN)
        temporal_regions = f"24/7 availability; Response time: ~{0.5 if process['speed'] > 400 else 1.0}s first token; Process duration: Variable by {process['type'].lower()} complexity; Real-time execution"
        
        # BFO 6: Spatial Regions (WHERE)
        if "mistral" in process["model"].lower():
            spatial_base = "EU (GDPR compliant)"
        elif any(model in process["model"].lower() for model in ["grok", "chatgpt", "claude"]):
            spatial_base = "US-based"
        else:
            spatial_base = "Global"
        spatial_regions = f"Deployment: {spatial_base}; API endpoints: Distributed; Processing: {process['type'].lower()}-optimized infrastructure"
        
        # BFO 7: Information Entities (HOW-WE-KNOW)
        information_entities = f"{process['type'].title()} documentation; Performance metrics; {process['category']} specifications; Routing decisions; Quality assessments; Integration logs"
        
        return {
            "material_entities": material_entities,
            "qualities": qualities,
            "realizable_entities": realizable_entities,
            "processes": processes,
            "temporal_regions": temporal_regions,
            "spatial_regions": spatial_regions,
            "information_entities": information_entities
        }
    
    def _analyze_competitive_advantage(self, process: Dict[str, Any]) -> str:
        """Analyze the competitive advantage of this granular process."""
        
        if process["exclusivity"] == "EXCLUSIVE":
            if "GROK" in process["name"]:
                return "Only model with truth-seeking architecture and highest intelligence (73)"
            elif "CLAUDE" in process["name"]:
                return "Exclusive Constitutional AI and safety-first design"
            elif "GEMINI" in process["name"]:
                return "Only major LLM with native multimodal capabilities"
            elif "MISTRAL" in process["name"]:
                return "Only European AI with GDPR compliance by design"
            else:
                return f"Exclusive {process['type'].lower()} capability"
        elif process["type"] == "TOOL":
            return f"Specialized {process['tools'][0].replace('_', ' ')} capability with cross-model compatibility"
        elif process["type"] == "WORKFLOW":
            return f"Multi-step {process['workflows'][0].replace('_', ' ')} orchestration across models"
        else:
            return f"{process['model'].upper()}-optimized implementation with specific performance characteristics"
    
    def _generate_specific_use_cases(self, process: Dict[str, Any]) -> str:
        """Generate specific use cases for this granular process."""
        
        use_case_map = {
            "truth_seeking": "Scientific fact verification; Contrarian analysis; Assumption challenging; Research validation",
            "real_time_search": "Current events analysis; Market research; News monitoring; Information retrieval",
            "native_image_generation": "Creative visuals; Product mockups; Marketing materials; Concept illustration",
            "constitutional_ai": "AI ethics assessment; Safety compliance; Regulatory analysis; Responsible AI deployment",
            "code_generation": "Software development; API creation; Algorithm implementation; Technical documentation",
            "massive_context": "Long document analysis; Comprehensive review; Large dataset processing; Context synthesis",
            "multimodal_analysis": "Cross-modal understanding; Video analysis; Image-text integration; Multimedia processing"
        }
        
        # Find matching use cases
        for key, use_cases in use_case_map.items():
            if key in process["name"].lower().replace(" ", "_"):
                return use_cases
        
        # Default based on type
        if process["type"] == "TOOL":
            return f"{process['name']} integration; API utilization; Tool-specific workflows; Automated processing"
        elif process["type"] == "WORKFLOW":
            return f"Multi-step {process['name'].lower()}; Process orchestration; Complex task automation; Integration workflows"
        else:
            return f"{process['model'].upper()}-specific applications; Optimized {process['category'].lower()} tasks; Model-native processing"
    
    def _describe_implementation(self, process: Dict[str, Any]) -> str:
        """Describe the technical implementation details."""
        
        if process["type"] == "MODEL_CORE":
            return f"Direct {process['model'].upper()} API integration; Model-specific optimization; Native capability utilization; Performance tuning"
        elif process["type"] == "TOOL":
            return f"{process['name']} API integration; Cross-model compatibility layer; Tool-specific protocols; Result standardization"
        else:  # WORKFLOW
            return "Multi-step orchestration engine; Model coordination; Process state management; Error handling and rollback"
    
    def _identify_integrations(self, process: Dict[str, Any]) -> str:
        """Identify key integration points for this process."""
        
        if process["type"] == "MODEL_CORE":
            return f"ABI Agent Framework; {process['model'].upper()} API; Supervisor routing; Model-specific tools"
        elif process["type"] == "TOOL":
            return "Tool API layer; Model abstraction; Result processing; Cross-tool coordination"
        else:  # WORKFLOW
            return "Workflow orchestrator; Multi-model coordination; State management; Process monitoring"
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary statistics for granular processes."""
        
        total_processes = len(self.granular_processes)
        
        # Type breakdown
        type_breakdown: Dict[str, int] = {}
        exclusivity_breakdown: Dict[str, int] = {}
        category_breakdown: Dict[str, int] = {}
        
        for process in self.granular_processes:
            # Type breakdown
            ptype = process["type"]
            type_breakdown[ptype] = type_breakdown.get(ptype, 0) + 1
            
            # Exclusivity breakdown
            exclusivity = process["exclusivity"]
            exclusivity_breakdown[exclusivity] = exclusivity_breakdown.get(exclusivity, 0) + 1
            
            # Category breakdown
            category = process["category"]
            category_breakdown[category] = category_breakdown.get(category, 0) + 1
        
        # Model participation analysis
        model_participation: Dict[str, int] = {}
        for process in self.granular_processes:
            models = process["model"].split(", ")
            for model in models:
                model = model.strip()
                model_participation[model] = model_participation.get(model, 0) + 1
        
        return {
            "total_processes": total_processes,
            "type_breakdown": type_breakdown,
            "exclusivity_breakdown": exclusivity_breakdown,
            "category_breakdown": category_breakdown,
            "model_participation": model_participation
        }


def main():
    """Generate granular Excel export and summary."""
    
    exporter = GranularBFOExporter()
    
    print("🧠 GRANULAR BFO PROCESS MAPPING EXCEL EXPORT")
    print("=" * 60)
    
    # Generate granular Excel export
    filename = exporter.generate_granular_excel_export()
    
    # Generate summary
    stats = exporter.generate_summary_report()
    
    print("\n📊 GRANULAR PROCESS SUMMARY:")
    print(f"   - Total Granular Processes: {stats['total_processes']}")
    print(f"   - Process Types: {len(stats['type_breakdown'])}")
    print(f"   - Categories: {len(stats['category_breakdown'])}")
    print(f"   - Exclusivity Levels: {len(stats['exclusivity_breakdown'])}")
    
    print("\n📈 PROCESS TYPE BREAKDOWN:")
    for ptype, count in sorted(stats['type_breakdown'].items()):
        print(f"   - {ptype}: {count} processes")
    
    print("\n🔒 EXCLUSIVITY BREAKDOWN:")
    for exclusivity, count in sorted(stats['exclusivity_breakdown'].items()):
        print(f"   - {exclusivity}: {count} processes")
    
    print("\n📂 CATEGORY BREAKDOWN:")
    for category, count in sorted(stats['category_breakdown'].items()):
        print(f"   - {category}: {count} processes")
    
    print("\n🤖 MODEL PARTICIPATION:")
    for model, count in sorted(stats['model_participation'].items(), key=lambda x: x[1], reverse=True):
        print(f"   - {model.upper()}: {count} processes")
    
    print(f"\n✅ Granular Excel file ready: {filename}")
    print("   Open in Excel/Google Sheets for detailed BFO verification")


if __name__ == "__main__":
    main()