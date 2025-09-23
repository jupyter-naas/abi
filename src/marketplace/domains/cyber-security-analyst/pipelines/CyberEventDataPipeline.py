"""
Cyber Security Event Data Pipeline

This pipeline downloads HTML content for cyber security events, stores them in a symmetrical
folder structure, and maps the data to the D3FEND ontology for agent interaction.
"""
# type: ignore

import yaml
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CyberEventDataPipeline:
    """Pipeline for downloading and processing cyber security event data."""
    
    def __init__(self, 
                 events_yaml_path: str = "events.yaml",
                 storage_base_path: str = "/Users/jrvmac/abi/storage/datastore/cyber",
                 d3fend_ontology_path: str = "legacy/ontologies/d3fend.ttl"):
        """
        Initialize the pipeline.
        
        Args:
            events_yaml_path: Path to the events.yaml file
            storage_base_path: Base path for storing downloaded data
            d3fend_ontology_path: Path to D3FEND ontology file
        """
        self.events_yaml_path = events_yaml_path
        self.storage_base_path = Path(storage_base_path)
        self.d3fend_ontology_path = d3fend_ontology_path
        
        # Create storage directory if it doesn't exist
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        
        # HTTP session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def load_events(self) -> List[Dict[str, Any]]:
        """Load events from the YAML file."""
        try:
            with open(self.events_yaml_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                return data.get('events', [])
        except FileNotFoundError:
            logger.error(f"Events file not found: {self.events_yaml_path}")
            return []
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            return []
    
    def create_event_storage_path(self, event: Dict[str, Any]) -> Path:
        """Create storage path for an event based on its metadata."""
        event_id = event.get('id', 'unknown')
        event_date = event.get('date', '2025-01-01')
        event_category = event.get('category', 'general')
        
        # Create hierarchical structure: year/month/category/event_id
        year = event_date.split('-')[0]
        month = event_date.split('-')[1]
        
        event_path = self.storage_base_path / year / month / event_category / event_id
        event_path.mkdir(parents=True, exist_ok=True)
        
        return event_path
    
    def download_html_content(self, url: str, timeout: int = 30) -> Optional[str]:
        """
        Download HTML content from a URL.
        
        Args:
            url: URL to download
            timeout: Request timeout in seconds
            
        Returns:
            HTML content as string or None if failed
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Try to get encoding from response headers
            encoding = response.encoding or 'utf-8'
            return response.content.decode(encoding, errors='ignore')
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to download {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading {url}: {e}")
            return None
    
    def extract_metadata_from_html(self, html_content: str, url: str) -> Dict[str, Any]:
        """Extract metadata from HTML content."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            metadata = {
                'title': '',
                'description': '',
                'keywords': [],
                'author': '',
                'published_date': '',
                'content_length': len(html_content),
                'url': url,
                'extracted_at': datetime.now().isoformat()
            }
            
            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.get_text().strip()
            
            # Extract meta description
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                metadata['description'] = desc_tag.get('content', '').strip()
            
            # Extract keywords
            keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
            if keywords_tag:
                keywords = keywords_tag.get('content', '')
                metadata['keywords'] = [k.strip() for k in keywords.split(',')]
            
            # Extract author
            author_tag = soup.find('meta', attrs={'name': 'author'})
            if author_tag:
                metadata['author'] = author_tag.get('content', '').strip()
            
            # Extract published date (various formats)
            date_selectors = [
                'meta[property="article:published_time"]',
                'meta[name="publish-date"]',
                'meta[name="date"]',
                'time[datetime]'
            ]
            
            for selector in date_selectors:
                date_element = soup.select_one(selector)
                if date_element:
                    date_value = date_element.get('content') or date_element.get('datetime')
                    if date_value:
                        metadata['published_date'] = date_value
                        break
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata from HTML: {e}")
            return {'url': url, 'error': str(e)}
    
    def map_to_d3fend(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map event data to D3FEND ontology concepts.
        
        Args:
            event: Event dictionary
            
        Returns:
            D3FEND mapping dictionary
        """
        d3fend_mapping = {
            'event_id': event.get('id'),
            'attack_vectors': event.get('attack_vectors', []),
            'd3fend_techniques': event.get('d3fend_techniques', []),
            'defensive_measures': [],
            'attack_patterns': [],
            'mitigations': []
        }
        
        # Map attack vectors to D3FEND defensive techniques
        attack_vector_mappings = {
            'supply_chain_compromise': ['D3-SWID', 'D3-HBPI', 'D3-CSPP'],
            'phishing': ['D3-EMAC', 'D3-CSPP', 'D3-ANCI'],
            'ransomware': ['D3-BDI', 'D3-DNSL', 'D3-FBA'],
            'ddos_attack': ['D3-NTF', 'D3-RTSD', 'D3-DNSL'],
            'malware': ['D3-HBPI', 'D3-SWID', 'D3-CSPP'],
            'credential_stuffing': ['D3-ANCI', 'D3-MFA', 'D3-CSPP'],
            'zero_day_exploitation': ['D3-SWID', 'D3-HBPI', 'D3-CSPP'],
            'lateral_movement': ['D3-NTF', 'D3-CSPP', 'D3-RTSD'],
            'data_exfiltration': ['D3-CSPP', 'D3-ANCI', 'D3-BDI']
        }
        
        # Add defensive measures based on attack vectors
        for attack_vector in event.get('attack_vectors', []):
            if attack_vector in attack_vector_mappings:
                d3fend_mapping['defensive_measures'].extend(
                    attack_vector_mappings[attack_vector]
                )
        
        # Remove duplicates
        d3fend_mapping['defensive_measures'] = list(set(d3fend_mapping['defensive_measures']))
        
        # Add MITRE ATT&CK mappings if available
        attack_pattern_mappings = {
            'supply_chain_compromise': ['T1195'],
            'phishing': ['T1566'],
            'ransomware': ['T1486'],
            'credential_stuffing': ['T1110'],
            'lateral_movement': ['T1021'],
            'data_exfiltration': ['T1041']
        }
        
        for attack_vector in event.get('attack_vectors', []):
            if attack_vector in attack_pattern_mappings:
                d3fend_mapping['attack_patterns'].extend(
                    attack_pattern_mappings[attack_vector]
                )
        
        d3fend_mapping['attack_patterns'] = list(set(d3fend_mapping['attack_patterns']))
        
        return d3fend_mapping
    
    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single cyber security event.
        
        Args:
            event: Event dictionary from YAML
            
        Returns:
            Processing results dictionary
        """
        logger.info(f"Processing event: {event.get('name', 'Unknown')}")
        
        # Create storage path
        event_path = self.create_event_storage_path(event)
        
        # Initialize results
        results = {
            'event_id': event.get('id'),
            'event_name': event.get('name'),
            'storage_path': str(event_path),
            'downloaded_sources': [],
            'failed_sources': [],
            'd3fend_mapping': None,
            'processed_at': datetime.now().isoformat()
        }
        
        # Download sources
        sources = event.get('sources', [])
        for i, source in enumerate(sources):
            url = source.get('url')
            title = source.get('title', f'Source {i+1}')
            
            if not url:
                continue
            
            logger.info(f"Downloading: {title}")
            
            # Download HTML content
            html_content = self.download_html_content(url)
            
            if html_content:
                # Create filename from URL
                parsed_url = urlparse(url)
                filename = f"source_{i+1}_{parsed_url.netloc}.html"
                file_path = event_path / filename
                
                # Save HTML content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Extract and save metadata
                metadata = self.extract_metadata_from_html(html_content, url)
                metadata_path = event_path / f"source_{i+1}_metadata.json"
                
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                
                results['downloaded_sources'].append({
                    'title': title,
                    'url': url,
                    'file_path': str(file_path),
                    'metadata_path': str(metadata_path),
                    'content_length': len(html_content)
                })
                
                logger.info(f"Successfully downloaded and saved: {title}")
            else:
                results['failed_sources'].append({
                    'title': title,
                    'url': url,
                    'error': 'Failed to download content'
                })
                logger.warning(f"Failed to download: {title}")
            
            # Add delay between requests to be respectful
            time.sleep(2)
        
        # Create D3FEND mapping
        d3fend_mapping = self.map_to_d3fend(event)
        results['d3fend_mapping'] = d3fend_mapping
        
        # Save D3FEND mapping
        d3fend_path = event_path / "d3fend_mapping.json"
        with open(d3fend_path, 'w', encoding='utf-8') as f:
            json.dump(d3fend_mapping, f, indent=2, ensure_ascii=False)
        
        # Save event metadata
        event_metadata_path = event_path / "event_metadata.json"
        with open(event_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(event, f, indent=2, ensure_ascii=False)
        
        # Save processing results
        results_path = event_path / "processing_results.json"
        with open(results_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return results
    
    def run_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete pipeline for all events.
        
        Returns:
            Pipeline execution results
        """
        logger.info("Starting Cyber Event Data Pipeline")
        
        # Load events
        events = self.load_events()
        if not events:
            logger.error("No events found to process")
            return {'error': 'No events found'}
        
        logger.info(f"Found {len(events)} events to process")
        
        # Initialize pipeline results
        pipeline_results = {
            'total_events': len(events),
            'processed_events': [],
            'failed_events': [],
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'storage_base_path': str(self.storage_base_path)
        }
        
        # Process each event
        for event in events:
            try:
                result = self.process_event(event)
                pipeline_results['processed_events'].append(result)
            except Exception as e:
                logger.error(f"Failed to process event {event.get('id', 'unknown')}: {e}")
                pipeline_results['failed_events'].append({
                    'event_id': event.get('id'),
                    'event_name': event.get('name'),
                    'error': str(e)
                })
        
        pipeline_results['completed_at'] = datetime.now().isoformat()
        
        # Save pipeline results
        pipeline_results_path = self.storage_base_path / "pipeline_results.json"
        with open(pipeline_results_path, 'w', encoding='utf-8') as f:
            json.dump(pipeline_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Pipeline completed. Processed {len(pipeline_results['processed_events'])} events successfully")
        
        return pipeline_results
    
    def create_agent_dataset_summary(self) -> Dict[str, Any]:
        """
        Create a summary dataset for agent interaction.
        
        Returns:
            Dataset summary for agent queries
        """
        events = self.load_events()
        
        summary = {
            'dataset_info': {
                'name': 'Cyber Security Events 2025',
                'description': 'Comprehensive dataset of major cyber security events in 2025',
                'total_events': len(events),
                'coverage_period': '2025-01-01 to 2025-12-30',
                'last_updated': datetime.now().isoformat()
            },
            'event_categories': {},
            'affected_sectors': {},
            'attack_vectors': {},
            'd3fend_techniques': {},
            'severity_distribution': {},
            'timeline': []
        }
        
        # Analyze events
        for event in events:
            # Categories
            category = event.get('category', 'unknown')
            summary['event_categories'][category] = summary['event_categories'].get(category, 0) + 1
            
            # Sectors
            for sector in event.get('affected_sectors', []):
                summary['affected_sectors'][sector] = summary['affected_sectors'].get(sector, 0) + 1
            
            # Attack vectors
            for vector in event.get('attack_vectors', []):
                summary['attack_vectors'][vector] = summary['attack_vectors'].get(vector, 0) + 1
            
            # D3FEND techniques
            for technique in event.get('d3fend_techniques', []):
                summary['d3fend_techniques'][technique] = summary['d3fend_techniques'].get(technique, 0) + 1
            
            # Severity
            severity = event.get('severity', 'unknown')
            summary['severity_distribution'][severity] = summary['severity_distribution'].get(severity, 0) + 1
            
            # Timeline
            summary['timeline'].append({
                'date': event.get('date'),
                'event_id': event.get('id'),
                'name': event.get('name'),
                'severity': event.get('severity'),
                'category': event.get('category')
            })
        
        # Sort timeline by date
        summary['timeline'].sort(key=lambda x: x['date'])
        
        # Save summary
        summary_path = self.storage_base_path / "dataset_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return summary


def main():
    """Main function to run the pipeline."""
    # Initialize pipeline
    pipeline = CyberEventDataPipeline(
        events_yaml_path="events.yaml",
        storage_base_path="/Users/jrvmac/abi/storage/datastore/cyber"
    )
    
    # Run pipeline
    results = pipeline.run_pipeline()
    
    # Create agent dataset summary
    summary = pipeline.create_agent_dataset_summary()
    
    print("Pipeline completed successfully!")
    print(f"Processed {len(results.get('processed_events', []))} events")
    print(f"Failed {len(results.get('failed_events', []))} events")
    print(f"Data stored in: {results.get('storage_base_path')}")
    print(f"Dataset summary created with {summary['dataset_info']['total_events']} events")


if __name__ == "__main__":
    main()
