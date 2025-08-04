"""
Capability Extraction System

This module extracts capabilities from model READMEs and derives processes
from those capabilities using a bottom-up approach.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelCapability:
    """Represents a specific capability of an AI model."""
    name: str
    description: str
    model_source: str
    confidence_level: float  # 0-1 scale
    evidence_text: str


@dataclass
class DerivedProcess:
    """Represents a process derived from model capabilities."""
    name: str
    description: str
    required_capabilities: List[str]
    supporting_models: List[str]
    process_category: str
    complexity_level: int  # 1-5 scale


class CapabilityExtractor:
    """Extracts capabilities from model documentation and derives processes."""
    
    def __init__(self):
        self.models_path = Path("src/core/modules")
        self.extracted_capabilities: Dict[str, List[ModelCapability]] = {}
        self.derived_processes: List[DerivedProcess] = []
        
    def extract_capabilities_from_readme(self, model_name: str, readme_content: str) -> List[ModelCapability]:
        """Extract capabilities from a model's README content."""
        capabilities = []
        
        # Define capability extraction patterns
        capability_patterns = [
            # Direct capability statements
            r"(?:capabilities?|excels? (?:in|at)|specializ[es]d? (?:in|for)|optimized for)[\s:]*([^.!\n]+)",
            
            # Feature bullets
            r"- \*\*([^*]+)\*\*:?\s*([^.\n]+)",
            
            # Section headers that indicate capabilities
            r"### \*\*([^*]+)\*\*\s*\n([^#]+?)(?=\n#|\Z)",
            
            # Core strengths
            r"(?:Core Strengths?|Key Features?|Unique Features?)[\s\n:]*([^#]+?)(?=\n#|\Z)",
            
            # What it can do
            r"(?:can|able to|supports?|enables?|provides?)[\s:]*([^.!\n]+(?:generation|analysis|processing|reasoning|search|computation|understanding|integration|management))",
        ]
        
        for pattern in capability_patterns:
            matches = re.finditer(pattern, readme_content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                if len(match.groups()) == 1:
                    capability_text = match.group(1).strip()
                else:
                    capability_name = match.group(1).strip()
                    capability_desc = match.group(2).strip() if len(match.groups()) > 1 else ""
                    capability_text = f"{capability_name}: {capability_desc}" if capability_desc else capability_name
                
                # Clean and validate capability
                capability_text = self._clean_capability_text(capability_text)
                if self._is_valid_capability(capability_text):
                    capabilities.append(ModelCapability(
                        name=self._extract_capability_name(capability_text),
                        description=capability_text,
                        model_source=model_name,
                        confidence_level=self._calculate_confidence(capability_text, readme_content),
                        evidence_text=match.group(0)[:200] + "..." if len(match.group(0)) > 200 else match.group(0)
                    ))
        
        return capabilities
    
    def _clean_capability_text(self, text: str) -> str:
        """Clean and normalize capability text."""
        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing punctuation
        text = text.strip(' :-•')
        
        return text
    
    def _is_valid_capability(self, text: str) -> bool:
        """Determine if text represents a valid capability."""
        if len(text) < 5 or len(text) > 200:
            return False
        
        # Must contain capability-indicating words
        capability_keywords = [
            'generation', 'analysis', 'processing', 'reasoning', 'search', 'computation',
            'understanding', 'integration', 'management', 'optimization', 'modeling',
            'synthesis', 'translation', 'conversation', 'instruction', 'creative',
            'mathematical', 'scientific', 'technical', 'multimodal', 'ethical',
            'compliance', 'truth-seeking', 'real-time', 'document', 'image',
            'code', 'algorithm', 'visualization', 'communication'
        ]
        
        return any(keyword in text.lower() for keyword in capability_keywords)
    
    def _extract_capability_name(self, text: str) -> str:
        """Extract a concise capability name from capability text."""
        # Look for the core capability term
        capability_terms = [
            'image generation', 'code generation', 'text generation',
            'data analysis', 'document analysis', 'market analysis', 'ethical analysis',
            'real-time search', 'web search', 'information search',
            'mathematical reasoning', 'logical reasoning', 'scientific reasoning',
            'multimodal processing', 'document processing', 'language processing',
            'conversation management', 'instruction following', 'task completion',
            'creative writing', 'technical writing', 'content creation',
            'truth-seeking', 'contrarian analysis', 'constitutional ai',
            'regulatory compliance', 'safety assessment', 'risk assessment'
        ]
        
        text_lower = text.lower()
        for term in capability_terms:
            if term in text_lower:
                return term.title()
        
        # Fallback: use first few words
        words = text.split()[:3]
        return ' '.join(words).title()
    
    def _calculate_confidence(self, capability_text: str, full_content: str) -> float:
        """Calculate confidence level for a capability based on evidence."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for explicit statements
        if any(word in capability_text.lower() for word in ['excels', 'specializes', 'optimized', 'designed for']):
            confidence += 0.3
        
        # Boost for unique/exclusive capabilities
        if any(word in capability_text.lower() for word in ['unique', 'only', 'exclusive', 'first', 'best']):
            confidence += 0.2
        
        # Boost for detailed descriptions
        if len(capability_text) > 50:
            confidence += 0.1
        
        # Boost for multiple mentions in content
        mention_count = full_content.lower().count(capability_text.lower()[:20])
        confidence += min(mention_count * 0.05, 0.15)
        
        return min(confidence, 1.0)
    
    def derive_processes_from_capabilities(self) -> List[DerivedProcess]:
        """Derive processes from extracted capabilities across all models."""
        # Group capabilities by similarity
        capability_groups = self._group_similar_capabilities()
        
        processes = []
        for group_name, capabilities in capability_groups.items():
            process = self._create_process_from_capability_group(group_name, capabilities)
            if process:
                processes.append(process)
        
        return processes
    
    def _group_similar_capabilities(self) -> Dict[str, List[ModelCapability]]:
        """Group similar capabilities across models."""
        groups: Dict[str, List[ModelCapability]] = {}
        
        # Flatten all capabilities
        all_capabilities = []
        for model_caps in self.extracted_capabilities.values():
            all_capabilities.extend(model_caps)
        
        # Define grouping keywords
        grouping_patterns = {
            'Image Generation': ['image', 'visual', 'graphic', 'picture', 'illustration'],
            'Code Generation': ['code', 'programming', 'algorithm', 'software', 'development'],
            'Mathematical Computation': ['mathematical', 'math', 'calculation', 'computation', 'numerical'],
            'Document Analysis': ['document', 'text analysis', 'reading', 'comprehension'],
            'Real-Time Search': ['search', 'web', 'internet', 'real-time', 'current'],
            'Ethical Reasoning': ['ethical', 'moral', 'constitutional', 'safety', 'compliance'],
            'Scientific Reasoning': ['scientific', 'research', 'analysis', 'reasoning', 'truth'],
            'Creative Writing': ['creative', 'writing', 'content', 'storytelling'],
            'Conversation Management': ['conversation', 'dialogue', 'chat', 'communication'],
            'Instruction Following': ['instruction', 'task', 'command', 'following'],
            'Multimodal Processing': ['multimodal', 'multi-modal', 'cross-modal', 'multimedia'],
            'Translation': ['translation', 'language', 'multilingual', 'translate'],
            'Data Processing': ['data', 'processing', 'analysis', 'computation'],
            'System Design': ['system', 'architecture', 'design', 'planning'],
            'Risk Assessment': ['risk', 'assessment', 'evaluation', 'analysis'],
            'Strategic Planning': ['strategic', 'planning', 'strategy', 'roadmap'],
            'Technical Documentation': ['documentation', 'technical writing', 'specs'],
            'Research Synthesis': ['research', 'synthesis', 'summary', 'compilation']
        }
        
        for capability in all_capabilities:
            capability_text = capability.description.lower()
            capability_name = capability.name.lower()
            
            # Find best matching group
            best_match = None
            best_score = 0
            
            for group_name, keywords in grouping_patterns.items():
                score = sum(1 for keyword in keywords if keyword in capability_text or keyword in capability_name)
                if score > best_score:
                    best_score = score
                    best_match = group_name
            
            # If no strong match, create new group based on capability name
            if best_score == 0:
                best_match = capability.name
            
            if best_match is not None:
                if best_match not in groups:
                    groups[best_match] = []
                groups[best_match].append(capability)
        
        return groups
    
    def _create_process_from_capability_group(self, group_name: str, capabilities: List[ModelCapability]) -> Optional[DerivedProcess]:
        """Create a process definition from a group of similar capabilities."""
        if not capabilities:
            return None
        
        # Extract supporting models
        supporting_models = list(set(cap.model_source for cap in capabilities))
        
        # Calculate complexity based on number of models and capability descriptions
        complexity = min(len(supporting_models), 5)
        
        # Generate process description
        process_description = f"Process involving {group_name.lower()} capabilities. " + \
                            f"Supported by {len(supporting_models)} models: {', '.join(supporting_models[:3])}{'...' if len(supporting_models) > 3 else ''}."
        
        # Determine process category
        process_category = self._determine_process_category(group_name, capabilities)
        
        # Extract required capabilities
        required_capabilities = [cap.name for cap in capabilities if cap.confidence_level > 0.7]
        
        return DerivedProcess(
            name=group_name,
            description=process_description,
            required_capabilities=required_capabilities,
            supporting_models=supporting_models,
            process_category=process_category,
            complexity_level=complexity
        )
    
    def _determine_process_category(self, group_name: str, capabilities: List[ModelCapability]) -> str:
        """Determine the category of a process based on its capabilities."""
        category_keywords = {
            'Creative': ['creative', 'generation', 'writing', 'image', 'content'],
            'Analytical': ['analysis', 'reasoning', 'research', 'assessment'],
            'Technical': ['code', 'programming', 'system', 'algorithm', 'mathematical'],
            'Communication': ['conversation', 'translation', 'documentation', 'instruction'],
            'Information': ['search', 'document', 'data', 'processing', 'synthesis'],
            'Cognitive': ['reasoning', 'thinking', 'problem-solving', 'planning'],
            'Interactive': ['chat', 'dialogue', 'assistance', 'following'],
            'Specialized': ['ethical', 'scientific', 'truth-seeking', 'compliance']
        }
        
        group_lower = group_name.lower()
        capability_text = ' '.join(cap.description.lower() for cap in capabilities)
        
        best_category = 'General'
        best_score = 0
        
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in group_lower or keyword in capability_text)
            if score > best_score:
                best_score = score
                best_category = category
        
        return best_category
    
    def extract_all_model_capabilities(self) -> Dict[str, List[ModelCapability]]:
        """Extract capabilities from all model READMEs."""
        for model_dir in self.models_path.iterdir():
            if model_dir.is_dir() and model_dir.name not in ['__pycache__', '.git']:
                readme_path = model_dir / "README.md"
                if readme_path.exists():
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    capabilities = self.extract_capabilities_from_readme(model_dir.name, content)
                    self.extracted_capabilities[model_dir.name] = capabilities
        
        return self.extracted_capabilities
    
    def generate_capability_report(self) -> str:
        """Generate a comprehensive report of extracted capabilities and derived processes."""
        report = []
        report.append("# AI Model Capability Extraction Report\n")
        
        # Summary
        total_capabilities = sum(len(caps) for caps in self.extracted_capabilities.values())
        report.append("## Summary")
        report.append(f"- **Models Analyzed**: {len(self.extracted_capabilities)}")
        report.append(f"- **Total Capabilities Extracted**: {total_capabilities}")
        report.append(f"- **Processes Derived**: {len(self.derived_processes)}")
        report.append("")
        
        # Capabilities by model
        report.append("## Capabilities by Model\n")
        for model_name, capabilities in self.extracted_capabilities.items():
            report.append(f"### {model_name.title()}")
            report.append(f"**{len(capabilities)} capabilities identified:**")
            for cap in sorted(capabilities, key=lambda x: x.confidence_level, reverse=True):
                confidence_stars = "⭐" * int(cap.confidence_level * 5)
                report.append(f"- **{cap.name}** {confidence_stars}")
                report.append(f"  - *{cap.description}*")
            report.append("")
        
        # Derived processes
        report.append("## Derived Processes\n")
        processes_by_category: Dict[str, List[DerivedProcess]] = {}
        for process in self.derived_processes:
            if process.process_category not in processes_by_category:
                processes_by_category[process.process_category] = []
            processes_by_category[process.process_category].append(process)
        
        for category, processes in processes_by_category.items():
            report.append(f"### {category} Processes")
            for process in sorted(processes, key=lambda x: len(x.supporting_models), reverse=True):
                complexity_dots = "●" * process.complexity_level
                report.append(f"- **{process.name}** {complexity_dots}")
                report.append(f"  - *{process.description}*")
                report.append(f"  - **Models**: {', '.join(process.supporting_models)}")
                report.append(f"  - **Required Capabilities**: {', '.join(process.required_capabilities[:3])}{'...' if len(process.required_capabilities) > 3 else ''}")
            report.append("")
        
        return "\n".join(report)
    
    def run_full_analysis(self) -> Tuple[Dict[str, List[ModelCapability]], List[DerivedProcess]]:
        """Run complete capability extraction and process derivation."""
        print("🔍 Extracting capabilities from model READMEs...")
        self.extract_all_model_capabilities()
        
        print("🧠 Deriving processes from capabilities...")
        self.derived_processes = self.derive_processes_from_capabilities()
        
        print("📊 Analysis complete!")
        print(f"   - {len(self.extracted_capabilities)} models analyzed")
        print(f"   - {sum(len(caps) for caps in self.extracted_capabilities.values())} capabilities extracted")
        print(f"   - {len(self.derived_processes)} processes derived")
        
        return self.extracted_capabilities, self.derived_processes


if __name__ == "__main__":
    extractor = CapabilityExtractor()
    capabilities, processes = extractor.run_full_analysis()
    
    # Generate and save report
    report = extractor.generate_capability_report()
    with open("docs/ontology/Capability_Analysis_Report.md", "w") as f:
        f.write(report)
    
    print("\n📄 Report saved to: docs/ontology/Capability_Analysis_Report.md")