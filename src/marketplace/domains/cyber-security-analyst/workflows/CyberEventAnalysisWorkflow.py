"""
Cyber Event Analysis Workflow

This workflow enables agents to interact with the cyber security events dataset,
providing analysis capabilities and D3FEND-based defensive recommendations.
"""
# type: ignore

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

class CyberEventAnalysisWorkflow:
    """Workflow for analyzing cyber security events and providing defensive insights."""
    
    def __init__(self, storage_base_path: str = "/Users/jrvmac/abi/storage/datastore/cyber"):
        """
        Initialize the workflow.
        
        Args:
            storage_base_path: Base path where cyber event data is stored
        """
        self.storage_base_path = Path(storage_base_path)
        self.dataset_summary = self._load_dataset_summary()
        
    def _load_dataset_summary(self) -> Dict[str, Any]:
        """Load the dataset summary for quick access."""
        summary_path = self.storage_base_path / "dataset_summary.json"
        if summary_path.exists():
            with open(summary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_dataset_overview(self) -> Dict[str, Any]:
        """
        Get an overview of the cyber security events dataset.
        
        Returns:
            Dataset overview information
        """
        if not self.dataset_summary:
            return {"error": "Dataset summary not available"}
        
        overview = {
            "dataset_info": self.dataset_summary.get("dataset_info", {}),
            "statistics": {
                "total_events": self.dataset_summary.get("dataset_info", {}).get("total_events", 0),
                "categories": len(self.dataset_summary.get("event_categories", {})),
                "affected_sectors": len(self.dataset_summary.get("affected_sectors", {})),
                "attack_vectors": len(self.dataset_summary.get("attack_vectors", {})),
                "d3fend_techniques": len(self.dataset_summary.get("d3fend_techniques", {}))
            },
            "top_categories": dict(sorted(
                self.dataset_summary.get("event_categories", {}).items(),
                key=lambda x: x[1], reverse=True
            )[:5]),
            "top_sectors": dict(sorted(
                self.dataset_summary.get("affected_sectors", {}).items(),
                key=lambda x: x[1], reverse=True
            )[:5]),
            "severity_distribution": self.dataset_summary.get("severity_distribution", {})
        }
        
        return overview
    
    def search_events_by_criteria(self, 
                                 category: Optional[str] = None,
                                 severity: Optional[str] = None,
                                 sector: Optional[str] = None,
                                 attack_vector: Optional[str] = None,
                                 date_range: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Search events based on various criteria.
        
        Args:
            category: Event category to filter by
            severity: Severity level to filter by
            sector: Affected sector to filter by
            attack_vector: Attack vector to filter by
            date_range: Tuple of (start_date, end_date) in YYYY-MM-DD format
            
        Returns:
            List of matching events
        """
        matching_events = []
        
        if not self.dataset_summary.get("timeline"):
            return matching_events
        
        for event_summary in self.dataset_summary["timeline"]:
            event_id = event_summary.get("event_id")
            if not event_id:
                continue
            
            # Load full event data
            event_data = self._load_event_data(event_id)
            if not event_data:
                continue
            
            # Apply filters
            if category and event_data.get("category") != category:
                continue
            
            if severity and event_data.get("severity") != severity:
                continue
            
            if sector and sector not in event_data.get("affected_sectors", []):
                continue
            
            if attack_vector and attack_vector not in event_data.get("attack_vectors", []):
                continue
            
            if date_range:
                event_date = event_data.get("date")
                if event_date and (event_date < date_range[0] or event_date > date_range[1]):
                    continue
            
            matching_events.append(event_data)
        
        return matching_events
    
    def _load_event_data(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Load full event data by event ID."""
        # Find event directory
        for year_dir in self.storage_base_path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                
                for category_dir in month_dir.iterdir():
                    if not category_dir.is_dir():
                        continue
                    
                    event_dir = category_dir / event_id
                    if event_dir.exists():
                        metadata_path = event_dir / "event_metadata.json"
                        if metadata_path.exists():
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                return json.load(f)
        
        return None
    
    def get_d3fend_analysis(self, event_id: str) -> Dict[str, Any]:
        """
        Get D3FEND analysis for a specific event.
        
        Args:
            event_id: Event identifier
            
        Returns:
            D3FEND analysis including defensive recommendations
        """
        # Find and load D3FEND mapping
        for year_dir in self.storage_base_path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue
            
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                
                for category_dir in month_dir.iterdir():
                    if not category_dir.is_dir():
                        continue
                    
                    event_dir = category_dir / event_id
                    if event_dir.exists():
                        d3fend_path = event_dir / "d3fend_mapping.json"
                        if d3fend_path.exists():
                            with open(d3fend_path, 'r', encoding='utf-8') as f:
                                d3fend_data = json.load(f)
                            
                            # Enhance with defensive recommendations
                            return self._enhance_d3fend_analysis(d3fend_data)
        
        return {"error": f"D3FEND analysis not found for event {event_id}"}
    
    def _enhance_d3fend_analysis(self, d3fend_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance D3FEND analysis with detailed defensive recommendations."""
        
        # D3FEND technique descriptions
        d3fend_descriptions = {
            "D3-SWID": {
                "name": "Software Identification",
                "description": "Identify and catalog software components to detect unauthorized changes",
                "category": "Asset Identification"
            },
            "D3-HBPI": {
                "name": "Host-based Process Inspection",
                "description": "Monitor and analyze process behavior on endpoints",
                "category": "Process Analysis"
            },
            "D3-CSPP": {
                "name": "Credential Security Policy",
                "description": "Implement and enforce credential security policies",
                "category": "Credential Analysis"
            },
            "D3-ANCI": {
                "name": "Authentication Cache Invalidation",
                "description": "Invalidate authentication caches to prevent credential reuse",
                "category": "Credential Analysis"
            },
            "D3-MFA": {
                "name": "Multi-Factor Authentication",
                "description": "Require multiple authentication factors for access",
                "category": "Authentication"
            },
            "D3-BDI": {
                "name": "Backup and Data Integrity",
                "description": "Maintain secure backups and verify data integrity",
                "category": "Data Backup"
            },
            "D3-DNSL": {
                "name": "DNS Sinkholing",
                "description": "Redirect malicious DNS queries to controlled servers",
                "category": "Network Isolation"
            },
            "D3-FBA": {
                "name": "File Backup Analysis",
                "description": "Analyze file backups for integrity and completeness",
                "category": "File Analysis"
            },
            "D3-NTF": {
                "name": "Network Traffic Filtering",
                "description": "Filter network traffic based on security policies",
                "category": "Network Isolation"
            },
            "D3-RTSD": {
                "name": "Real-time System Detection",
                "description": "Detect threats in real-time through system monitoring",
                "category": "System Activity Analysis"
            },
            "D3-EMAC": {
                "name": "Email Analysis and Classification",
                "description": "Analyze and classify email content for threats",
                "category": "Message Analysis"
            }
        }
        
        enhanced_analysis = {
            "event_id": d3fend_data.get("event_id"),
            "attack_summary": {
                "attack_vectors": d3fend_data.get("attack_vectors", []),
                "attack_patterns": d3fend_data.get("attack_patterns", [])
            },
            "defensive_techniques": [],
            "implementation_priority": [],
            "coverage_analysis": {},
            "recommendations": []
        }
        
        # Enhance defensive techniques with descriptions
        for technique in d3fend_data.get("defensive_measures", []):
            if technique in d3fend_descriptions:
                enhanced_analysis["defensive_techniques"].append({
                    "technique_id": technique,
                    "name": d3fend_descriptions[technique]["name"],
                    "description": d3fend_descriptions[technique]["description"],
                    "category": d3fend_descriptions[technique]["category"]
                })
        
        # Prioritize implementation based on attack vectors
        priority_mapping = {
            "supply_chain_compromise": ["D3-SWID", "D3-HBPI"],
            "phishing": ["D3-EMAC", "D3-CSPP"],
            "ransomware": ["D3-BDI", "D3-DNSL"],
            "credential_stuffing": ["D3-MFA", "D3-ANCI"],
            "ddos_attack": ["D3-NTF", "D3-RTSD"]
        }
        
        for attack_vector in d3fend_data.get("attack_vectors", []):
            if attack_vector in priority_mapping:
                for technique in priority_mapping[attack_vector]:
                    if technique not in enhanced_analysis["implementation_priority"]:
                        enhanced_analysis["implementation_priority"].append(technique)
        
        # Generate recommendations
        enhanced_analysis["recommendations"] = self._generate_defensive_recommendations(
            d3fend_data.get("attack_vectors", []),
            enhanced_analysis["defensive_techniques"]
        )
        
        return enhanced_analysis
    
    def _generate_defensive_recommendations(self, 
                                         attack_vectors: List[str], 
                                         defensive_techniques: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate specific defensive recommendations based on attack vectors."""
        
        recommendations = []
        
        # General recommendations based on attack vectors
        vector_recommendations = {
            "supply_chain_compromise": [
                {
                    "priority": "High",
                    "action": "Implement software bill of materials (SBOM) tracking",
                    "description": "Maintain detailed inventory of all software components and dependencies"
                },
                {
                    "priority": "High", 
                    "action": "Deploy code signing verification",
                    "description": "Verify digital signatures of all software updates and installations"
                }
            ],
            "phishing": [
                {
                    "priority": "High",
                    "action": "Deploy advanced email security gateway",
                    "description": "Implement AI-powered email analysis to detect sophisticated phishing attempts"
                },
                {
                    "priority": "Medium",
                    "action": "Conduct regular phishing simulation training",
                    "description": "Train users to identify and report phishing attempts"
                }
            ],
            "ransomware": [
                {
                    "priority": "Critical",
                    "action": "Implement immutable backup strategy",
                    "description": "Deploy air-gapped, immutable backups with regular recovery testing"
                },
                {
                    "priority": "High",
                    "action": "Deploy endpoint detection and response (EDR)",
                    "description": "Monitor endpoint behavior for ransomware indicators"
                }
            ],
            "ddos_attack": [
                {
                    "priority": "High",
                    "action": "Deploy DDoS protection service",
                    "description": "Implement cloud-based DDoS mitigation with traffic scrubbing"
                },
                {
                    "priority": "Medium",
                    "action": "Configure rate limiting and traffic shaping",
                    "description": "Implement network-level controls to manage traffic volume"
                }
            ]
        }
        
        for attack_vector in attack_vectors:
            if attack_vector in vector_recommendations:
                recommendations.extend(vector_recommendations[attack_vector])
        
        return recommendations
    
    def get_threat_timeline(self, 
                           start_date: Optional[str] = None, 
                           end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get chronological timeline of cyber security events.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Chronological list of events
        """
        timeline = self.dataset_summary.get("timeline", [])
        
        if start_date or end_date:
            filtered_timeline = []
            for event in timeline:
                event_date = event.get("date")
                if not event_date:
                    continue
                
                if start_date and event_date < start_date:
                    continue
                
                if end_date and event_date > end_date:
                    continue
                
                filtered_timeline.append(event)
            
            return filtered_timeline
        
        return timeline
    
    def get_sector_analysis(self, sector: str) -> Dict[str, Any]:
        """
        Get detailed analysis for a specific sector.
        
        Args:
            sector: Sector name to analyze
            
        Returns:
            Sector-specific threat analysis
        """
        sector_events = self.search_events_by_criteria(sector=sector)
        
        if not sector_events:
            return {"error": f"No events found for sector: {sector}"}
        
        analysis = {
            "sector": sector,
            "total_incidents": len(sector_events),
            "severity_breakdown": {},
            "attack_vector_frequency": {},
            "timeline": [],
            "defensive_recommendations": []
        }
        
        # Analyze events
        for event in sector_events:
            # Severity breakdown
            severity = event.get("severity", "unknown")
            analysis["severity_breakdown"][severity] = analysis["severity_breakdown"].get(severity, 0) + 1
            
            # Attack vector frequency
            for vector in event.get("attack_vectors", []):
                analysis["attack_vector_frequency"][vector] = analysis["attack_vector_frequency"].get(vector, 0) + 1
            
            # Timeline
            analysis["timeline"].append({
                "date": event.get("date"),
                "name": event.get("name"),
                "severity": event.get("severity"),
                "category": event.get("category")
            })
        
        # Sort timeline
        analysis["timeline"].sort(key=lambda x: x["date"])
        
        # Generate sector-specific recommendations
        top_vectors = sorted(analysis["attack_vector_frequency"].items(), key=lambda x: x[1], reverse=True)[:3]
        for vector, count in top_vectors:
            recommendations = self._generate_defensive_recommendations([vector], [])
            analysis["defensive_recommendations"].extend(recommendations)
        
        return analysis
    
    def query_dataset(self, query: str) -> Dict[str, Any]:
        """
        Natural language query interface for the dataset.
        
        Args:
            query: Natural language query about cyber security events
            
        Returns:
            Query results and analysis
        """
        query_lower = query.lower()
        
        # Simple keyword-based query processing
        if "overview" in query_lower or "summary" in query_lower:
            return self.get_dataset_overview()
        
        elif "timeline" in query_lower:
            return {"timeline": self.get_threat_timeline()}
        
        elif "ransomware" in query_lower:
            return {"ransomware_events": self.search_events_by_criteria(category="ransomware")}
        
        elif "phishing" in query_lower:
            return {"phishing_events": self.search_events_by_criteria(category="phishing")}
        
        elif "critical" in query_lower:
            return {"critical_events": self.search_events_by_criteria(severity="critical")}
        
        elif "healthcare" in query_lower:
            return self.get_sector_analysis("healthcare")
        
        elif "financial" in query_lower or "banking" in query_lower:
            return self.get_sector_analysis("financial_services")
        
        elif "government" in query_lower:
            return self.get_sector_analysis("government")
        
        else:
            return {
                "message": "Query not recognized. Try asking about: overview, timeline, ransomware, phishing, critical events, or specific sectors like healthcare, financial, or government."
            }


# Example usage functions for agent integration
def analyze_cyber_events(query: str = "overview") -> Dict[str, Any]:
    """
    Main function for agents to analyze cyber security events.
    
    Args:
        query: Analysis query or request
        
    Returns:
        Analysis results
    """
    workflow = CyberEventAnalysisWorkflow()
    return workflow.query_dataset(query)

def get_defensive_recommendations(event_id: str) -> Dict[str, Any]:
    """
    Get D3FEND-based defensive recommendations for a specific event.
    
    Args:
        event_id: Event identifier
        
    Returns:
        Defensive recommendations
    """
    workflow = CyberEventAnalysisWorkflow()
    return workflow.get_d3fend_analysis(event_id)
