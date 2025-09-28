#!/usr/bin/env python3
"""
Orchestration to Oxigraph Integration Script

This script monitors the RSS feed output from the orchestration system and transforms 
it into BFO-compliant RDF triples that are inserted into Oxigraph.
"""

import os
import json
import time
import glob
from typing import Dict, Any, List
from pathlib import Path
from rdflib import Graph
from datetime import datetime

from .RSSFeedToBFOPipeline import (
    RSSFeedToBFOPipeline,
    RSSFeedToBFOPipelineConfiguration,
    RSSFeedToBFOPipelineParameters
)

# Mock triple store service for testing
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from typing import Callable
import rdflib.query

class MockTripleStoreService(ITripleStoreService):
    def __init__(self):
        self.graphs = []
        
    def insert(self, graph: Graph):
        """Insert graph into triple store."""
        self.graphs.append(graph)
        print(f"📥 Inserted graph with {len(graph)} triples into triple store")
        return True
        
    def insert_graph(self, graph: Graph) -> bool:
        """Legacy method for compatibility."""
        return self.insert(graph)
        
    def get_graph_count(self) -> int:
        return len(self.graphs)
        
    def get_total_triples(self) -> int:
        return sum(len(graph) for graph in self.graphs)
        
    def remove(self, triples: Graph):
        pass
        
    def get(self) -> Graph:
        combined = Graph()
        for graph in self.graphs:
            combined += graph
        return combined
        
    def query(self, query: str) -> rdflib.query.Result:
        return self.get().query(query)
        
    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.get().query(query)
        
    def get_subject_graph(self, subject: str) -> Graph:
        return Graph()
        
    def subscribe(self, topic: tuple, event_type: OntologyEvent, callback: Callable) -> str:
        return "mock_subscription"
        
    def unsubscribe(self, subscription_id: str):
        pass
        
    def load_schema(self, filepath: str):
        pass
        
    def get_schema_graph(self) -> Graph:
        return Graph()

class OrchestrationToOxigraphProcessor:
    """Processes RSS feed files and sends them to Oxigraph via BFO pipeline."""
    
    def __init__(self, 
                 rss_feed_directory: str,
                 triple_store_service = None,
                 processed_files_log: str = "processed_files.txt"):
        self.rss_feed_directory = Path(rss_feed_directory)
        self.processed_files_log = Path(processed_files_log)
        
        # Initialize triple store service
        if triple_store_service is None:
            self.triple_store_service = MockTripleStoreService()
        else:
            self.triple_store_service = triple_store_service
            
        # Initialize BFO pipeline
        config = RSSFeedToBFOPipelineConfiguration(
            triple_store=self.triple_store_service
        )
        self.bfo_pipeline = RSSFeedToBFOPipeline(config)
        
        # Load processed files log
        self.processed_files = self._load_processed_files()
        
    def _load_processed_files(self) -> set:
        """Load list of already processed files."""
        if self.processed_files_log.exists():
            with open(self.processed_files_log, 'r') as f:
                return set(line.strip() for line in f)
        return set()
    
    def _save_processed_file(self, filename: str):
        """Add filename to processed files log."""
        with open(self.processed_files_log, 'a') as f:
            f.write(f"{filename}\n")
        self.processed_files.add(filename)
    
    def find_new_rss_files(self) -> List[Path]:
        """Find new RSS feed files that haven't been processed."""
        pattern = str(self.rss_feed_directory / "*.txt")
        all_files = glob.glob(pattern)
        
        new_files = []
        for file_path in all_files:
            filename = os.path.basename(file_path)
            if filename not in self.processed_files:
                new_files.append(Path(file_path))
                
        return new_files
    
    def load_rss_data(self, file_path: Path) -> Dict[str, Any]:
        """Load RSS data from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"❌ Error loading RSS data from {file_path}: {e}")
            return {}
    
    def process_rss_file(self, file_path: Path) -> bool:
        """Process a single RSS file through BFO pipeline."""
        print(f"🔄 Processing RSS file: {file_path.name}")
        
        # Load RSS data
        rss_data = self.load_rss_data(file_path)
        if not rss_data:
            return False
            
        try:
            # Create pipeline parameters
            collection_id = f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file_path.stem}"
            parameters = RSSFeedToBFOPipelineParameters(
                rss_data=rss_data,
                collection_id=collection_id
            )
            
            # Run BFO pipeline
            bfo_graph = self.bfo_pipeline.run(parameters)
            
            # Insert into triple store
            success = self.triple_store_service.insert_graph(bfo_graph)
            
            if success:
                # Mark as processed
                self._save_processed_file(file_path.name)
                print(f"✅ Successfully processed {file_path.name} -> {len(bfo_graph)} triples")
                
                # Generate SPARQL for inspection
                self._generate_sparql_output(bfo_graph, file_path.stem)
                
                return True
            else:
                print(f"❌ Failed to insert triples for {file_path.name}")
                return False
                
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            return False
    
    def _generate_sparql_output(self, graph: Graph, filename_stem: str):
        """Generate SPARQL INSERT DATA statement for inspection."""
        sparql_dir = Path("sparql_output")
        sparql_dir.mkdir(exist_ok=True)
        
        # Generate SPARQL
        prefixes = []
        for prefix, namespace in graph.namespaces():
            prefixes.append(f"PREFIX {prefix}: <{namespace}>")
        
        triples = []
        for subject, predicate, obj in graph:
            triple_line = f"    {subject.n3()} {predicate.n3()} {obj.n3()} ."
            triples.append(triple_line)
        
        sparql_content = "\n".join(prefixes) + "\n\nINSERT DATA {\n" + "\n".join(triples) + "\n}"
        
        # Save to file
        sparql_file = sparql_dir / f"{filename_stem}_insert.sparql"
        with open(sparql_file, 'w') as f:
            f.write(sparql_content)
        
        print(f"💾 Generated SPARQL file: {sparql_file}")
    
    def run_batch_processing(self) -> Dict[str, int]:
        """Process all new RSS files in batch."""
        new_files = self.find_new_rss_files()
        
        if not new_files:
            print("ℹ️  No new RSS files to process")
            return {"processed": 0, "failed": 0, "total_triples": 0}
        
        print(f"🎯 Found {len(new_files)} new RSS files to process")
        
        processed = 0
        failed = 0
        
        for file_path in new_files:
            if self.process_rss_file(file_path):
                processed += 1
            else:
                failed += 1
        
        total_triples = self.triple_store_service.get_total_triples()
        
        print("\n📊 Batch Processing Results:")
        print(f"   ✅ Processed: {processed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Total triples in store: {total_triples}")
        print(f"   📚 Total graphs in store: {self.triple_store_service.get_graph_count()}")
        
        return {
            "processed": processed,
            "failed": failed,
            "total_triples": total_triples
        }
    
    def run_continuous_monitoring(self, interval_seconds: int = 30):
        """Continuously monitor for new RSS files and process them."""
        print(f"🔄 Starting continuous monitoring (interval: {interval_seconds}s)")
        print(f"📂 Monitoring directory: {self.rss_feed_directory}")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                results = self.run_batch_processing()
                if results["processed"] > 0:
                    print(f"✅ Processed {results['processed']} files this cycle")
                
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
        except Exception as e:
            print(f"❌ Error in continuous monitoring: {e}")

def main():
    """Main function to run the orchestration to Oxigraph processor."""
    
    # Configuration
    RSS_FEED_DIR = "/Users/jrvmac/abi/storage/datastore/core/modules/abi/orchestration/rss_feed"
    
    print("🚀 RSS Feed to BFO Ontology Processor")
    print("====================================")
    print(f"📂 RSS Feed Directory: {RSS_FEED_DIR}")
    
    # Check if directory exists
    if not os.path.exists(RSS_FEED_DIR):
        print(f"❌ RSS feed directory not found: {RSS_FEED_DIR}")
        print("   Make sure orchestration system is running and generating files")
        return
    
    # Initialize processor
    processor = OrchestrationToOxigraphProcessor(
        rss_feed_directory=RSS_FEED_DIR,
        processed_files_log="processed_rss_files.txt"
    )
    
    # Run batch processing once
    print("\n🔄 Running initial batch processing...")
    results = processor.run_batch_processing()
    
    if results["processed"] > 0:
        print(f"\n🎉 Successfully processed {results['processed']} RSS files!")
        print(f"📈 Generated {results['total_triples']} BFO-compliant triples")
        print("💾 Check 'sparql_output/' directory for generated SPARQL files")
    
    # Ask user if they want continuous monitoring
    response = input("\n🤖 Would you like to start continuous monitoring? (y/n): ")
    if response.lower() in ['y', 'yes']:
        processor.run_continuous_monitoring(interval_seconds=60)

if __name__ == "__main__":
    main()